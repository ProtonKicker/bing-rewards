# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""The closed loop: search -> verify registration -> retry or stop.

A `Session` is anything that can sign-in-check, read rewards status, and run a
search — the real Selenium one or the dry-run mock. The collector only ever
counts a search as *registered* when live evidence (search-card progress, or
point increase as fallback) proves it, so a stalled round is detected instead
of silently burned.
"""

from __future__ import annotations

import logging
import random
import time
import urllib.parse
from typing import TYPE_CHECKING, Protocol

from bing_rewards import options as opts_mod
from bing_rewards import rewards
from bing_rewards.firefox import check_signed_in
from bing_rewards.queries import QueryGenerator

if TYPE_CHECKING:
    from bing_rewards.runlog import RunLog

logger = logging.getLogger(__name__)

# Rewards page health-check: if the dashboard shows one of these, it is
# unreadable and all verification signals will fail.
UNSUPPORT_MARKERS = (
    'does not support your browser',
    'rewards error',
    'something went wrong',
    'not supported',
)


class Session(Protocol):
    name: str
    driver: object | None = None  # RealSession has it; MockSession does not

    def signed_in(self) -> tuple[bool, str]: ...
    def rewards_healthy(self) -> bool: ...
    def status(self) -> rewards.Status: ...
    def search(self, query: str) -> None: ...


class RealSession:
    """Drives a live Firefox WebDriver."""

    def __init__(self, driver, name: str):
        self.driver = driver
        self.name = name

    def signed_in(self) -> tuple[bool, str]:
        return check_signed_in(self.driver)

    def status(self) -> rewards.Status:
        return rewards.read_status(self.driver)

    def search(self, query: str) -> None:
        url = opts_mod.BING_SEARCH_URL + urllib.parse.quote_plus(query)
        try:
            self.driver.get(url)
        except Exception as exc:
            # A busted navigation (e.g. geckodriver "network protocol error")
            # poisons the WebDriver for the rest of the session — re-raise so
            # the outer loop can decide whether to restart.
            raise RuntimeError(f'navigation failed for "{query}": {exc}') from exc
        # Dwell on results like a reader, then let the point event settle.
        time.sleep(random.uniform(2.5, 6.0))

    def rewards_healthy(self) -> bool:
        """Check if the rewards dashboard is readable (not blocked/errored)."""
        return _rewards_page_healthy(self.driver)

    def take_screenshot(self, path: str) -> bool:
        """Window-scoped capture: never includes the user's desktop."""
        try:
            return bool(self.driver.save_screenshot(path))
        except Exception as e:  # noqa: BLE001 - evidence only
            logger.debug('driver screenshot failed: %s', e)
            return False


class RoundResult:
    def __init__(self, kind: str):
        self.kind = kind
        self.skipped_reason: str | None = None
        self.target: int | None = None
        self.attempted = 0
        self.registered = 0
        self.wasted = 0
        self.complete = False
        self.stalled = False
        self.signed_in = False
        self.sign_in_detail = ''
        self.notes: list[str] = []


def _delay(opts: opts_mod.Options, penalty: float = 1.0) -> None:
    time.sleep(random.uniform(opts.min_delay, opts.max_delay) * penalty)


def run_round(  # noqa: PLR0912, PLR0915 - the verify/retry state machine is one coherent loop
    kind: str,
    session: Session,
    opts: opts_mod.Options,
    log: RunLog,
    shutter=None,
) -> RoundResult:
    """Run one rewards round (desktop or mobile) with per-batch verification."""
    result = RoundResult(kind)
    rlog = log.round(kind)

    if rlog.complete and not opts.force:
        result.skipped_reason = "already complete per today's run log"
        result.complete = True
        result.signed_in = True
        result.registered = rlog.registered
        log.event(f'{kind}: skipped ({result.skipped_reason})')
        return result

    ok, detail = session.signed_in()
    result.signed_in = ok
    result.sign_in_detail = detail
    if not ok:
        rlog.stalled = True
        log.event(f'{kind}: NOT signed in ({detail}) — aborting round')
        return result

    before = session.status()
    if log.points_before is None:
        log.points_before = before.points
    prog = before.progress(kind)
    fallback = opts.desktop_count if kind == 'desktop' else opts.mobile_count
    start_current = prog.current or 0
    result.target = prog.maximum or fallback
    if prog.maximum is None:
        result.notes.append(f'live quota unreadable; using fallback target {fallback}')
    rlog.target = result.target

    if prog.complete:
        result.complete = True
        rlog.complete = True
        log.event(f'{kind}: quota already complete ({start_current}/{result.target})')
        return result

    if shutter:
        shutter.capture(f'{kind}-before', session)

    # Warmup: brief pause to let session cookies/initial page state settle
    # before the first search request.  Avoids the "first search is always
    # wasted" observation from short runs.
    time.sleep(opts_mod.WARMUP_DELAY)

    # Early health check: verify rewards page is readable before burning
    # searches.  If the dashboard shows an "unsupported" / "error" page,
    # abort immediately instead of wasting a full round.
    if not _rewards_page_healthy(session):
        result.notes.append(
            'rewards page unhealthy before first search — aborting to avoid wasted searches'
        )
        result.stalled = True
        rlog.stalled = True
        log.event(f'{kind}: rewards page unhealthy — aborting round early')
        if shutter:
            shutter.capture(f'{kind}-unhealthy', session)
        return result

    queries = QueryGenerator()
    last_counter: int | None = before.counter(kind)
    last_points: int | None = before.points
    registered_total = 0
    attempted = 0
    stall_handled = False
    no_signal_batches = 0
    zero_delta_batches = 0
    # Absolute ceiling so a fully silent Bing page cannot loop forever, even
    # when --max-searches is not given.
    effective_max = opts.max_searches
    if effective_max is None:
        effective_max = result.target * opts_mod.DEFAULT_SEARCH_CAP_MULTIPLIER

    while True:
        remaining = result.target - (last_counter if last_counter is not None else registered_total)
        if remaining <= 0:
            result.complete = True
            break
        if attempted >= effective_max:
            result.notes.append(f'absolute search cap {effective_max} reached')
            break

        batch = min(opts.batch_size, remaining)
        batch = min(batch, effective_max - attempted)
        for _ in range(batch):
            query = queries.next()
            try:
                session.search(query)
            except RuntimeError as e:
                # Unrecoverable navigation error — quit this round.
                result.notes.append(f'navigation died mid-batch: {e}')
                log.event(f'{kind}: {e} — stopping round')
                result.stalled = True
                rlog.stalled = True
                break
            attempted += 1
            rlog.attempted += 1
            logger.debug('%s search %d: %s', kind, attempted, query)
            _delay(opts)
        if result.stalled:
            break

        after = session.status()
        counter_delta = _progress_delta(kind, before, last_counter, after)
        points_delta = _points_delta(last_points, after.points)
        logger.info(
            '%s: batch of %d done — progress delta %s, points delta %s',
            kind,
            batch,
            counter_delta,
            points_delta,
        )

        if counter_delta is not None and counter_delta > 0:
            registered_total += min(counter_delta, batch)
            last_counter = after.counter(kind) or last_counter
            rlog.registered = registered_total
            zero_delta_batches = 0
            no_signal_batches = 0
        elif points_delta is not None and points_delta > 0:
            # Counter missing: treat any point gain as the batch registering.
            registered_total += batch
            rlog.registered = registered_total
            zero_delta_batches = 0
            no_signal_batches = 0
            if after.progress(kind).maximum is None:
                result.notes.append('using point deltas (search counter unavailable)')
        elif (counter_delta is None and points_delta is None) or (points_delta is not None and points_delta == 0):
            # Unverifiable batch (no numeric signal at all), or medallion balance
            # reported zero change. The medallion cache can lag the actual balance
            # by tens of seconds — treat 0-delta batches as "no signal" for up to
            # MAX_NO_SIGNAL_BATCHES before declaring a stall, rather than
            # burning the round on the very first quiet batch.
            last_counter = after.counter(kind)
            last_points = after.points
            if points_delta == 0:
                zero_delta_batches += 1
            else:
                no_signal_batches += 1
            total_quiet = zero_delta_batches + no_signal_batches
            log.event(
                f'{kind}: batch #{total_quiet} with no increment '
                f'(source={after.source}, counter_delta={counter_delta}, '
                f'points_delta={points_delta})'
            )
            # On mobile the medallion may not render on search-result pages.
            if kind == 'mobile' and total_quiet >= 2:
                try:
                    session.driver.get('https://www.bing.com/')
                    time.sleep(2.0)
                except Exception:
                    pass
            if total_quiet >= opts_mod.MAX_NO_SIGNAL_BATCHES:
                result.notes.append(
                    f'stalled: {total_quiet} consecutive batches without increment '
                    f'(medallion may be cached) — stopping round'
                )
                result.stalled = True
                rlog.stalled = True
                break
            continue
        else:
            # Negative counter/points delta (shouldn't happen normally).
            if not stall_handled and opts.retry_rounds > 0:
                stall_handled = True
                queries.fresh()
                result.notes.append('anomalous delta; retrying with fresh queries + longer delays')
                log.event(f'{kind}: anomalous delta, retrying batch')
                _delay(opts, penalty=3.0)
                continue
            result.stalled = True
            rlog.stalled = True
            log.event(f'{kind}: stalled after {attempted} searches — stopping round')
            break

        stall_handled = False
        last_points = after.points
        log.points_after = after.points
        if after.progress(kind).complete:
            result.complete = True
            break

    result.attempted = attempted
    result.registered = registered_total
    result.wasted = attempted - registered_total
    rlog.wasted += attempted - registered_total
    if result.complete:
        rlog.complete = True
    log.event(
        f'{kind}: attempted={attempted} registered={registered_total} '
        f'{"complete" if result.complete else ("stalled" if result.stalled else "stopped")}'
    )
    if shutter:
        shutter.capture(f'{kind}-after', session)
    return result


def _progress_delta(
    kind: str, before: rewards.Status, last: int | None, after: rewards.Status
) -> int | None:
    cur = after.counter(kind)
    if cur is None:
        return None
    base = last if last is not None else before.counter(kind)
    if base is None:
        return None
    return cur - base


def _rewards_page_healthy(driver) -> bool:
    """Navigate to rewards.bing.com and confirm the dashboard is readable.

    Takes the raw driver (not a Session) so it can be called directly from
    RealSession.  Returns False if the page shows an 'unsupported browser',
    'Rewards Error', or any known blocking message.  The caller uses this to
    abort a round immediately instead of burning searches on a dead session.
    """
    try:
        driver.get(rewards.REWARDS_URL)
        time.sleep(2.0)
        page = (driver.page_source or '').lower()
        # Also check the medallion — if it's present, the page is usable.
        has_medallion = 'rh_rwm' in page or 'rewards-medallion' in page
        has_blocker = any(marker in page for marker in UNSUPPORT_MARKERS)
        if has_blocker and not has_medallion:
            logger.warning(
                'rewards page blocked: found error markers (no medallion present)'
            )
            return False
        return True
    except Exception as e:  # noqa: BLE001
        logger.debug('rewards health check failed: %s', e)
        return True  # optimistic: let the status-based flow decide


def _points_delta(last: int | None, now: int | None) -> int | None:
    if last is None or now is None:
        return None
    return now - last
