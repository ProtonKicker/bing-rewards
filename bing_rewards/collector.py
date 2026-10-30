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
    def status(self, force_refresh: bool = False) -> rewards.Status: ...
    def search(self, query: str) -> None: ...


class RealSession:
    """Drives a live Firefox WebDriver."""

    def __init__(self, driver, name: str):
        self.driver = driver
        self.name = name

    def signed_in(self) -> tuple[bool, str]:
        return check_signed_in(self.driver)

    def status(self, force_refresh: bool = False) -> rewards.Status:
        return rewards.read_status(self.driver, force_refresh=force_refresh)

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
    """Run one rewards round (desktop or mobile) with per-batch verification.

    Uses optimistic verification: if we performed searches on bing.com and the
    medallion doesn't immediately show an increase, we assume the searches
    registered but the balance display is cached. We re-verify with force
    refresh on demand, and only declare a stall after exhausting all patience
    and recovery options.
    """
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
    # Sanity cap: the live API occasionally returns monthly bonus numbers
    # (e.g. 3 500) instead of the daily search quota. Clamp to a sane max.
    sane_cap = 120 if kind == 'desktop' else 40
    if result.target > sane_cap:
        result.target = sane_cap
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

    # Wall-clock timeout to prevent infinite loops when Bing is unresponsive.
    import time as _time
    _round_start = _time.monotonic()
    _WALL_CLOCK_TIMEOUT = getattr(opts_mod, 'WALL_CLOCK_TIMEOUT', 300.0)

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
    optimistic_registered = 0  # searches done but not yet definitively verified
    # Absolute ceiling so a fully silent Bing page cannot loop forever, even
    # when --max-searches is not given.
    effective_max = opts.max_searches
    if effective_max is None:
        effective_max = result.target * opts_mod.DEFAULT_SEARCH_CAP_MULTIPLIER

    while True:
        if _time.monotonic() - _round_start > _WALL_CLOCK_TIMEOUT:
            result.notes.append(
                f'wall-clock timeout {_WALL_CLOCK_TIMEOUT:.0f}s reached — aborting round'
            )
            result.stalled = True
            rlog.stalled = True
            log.event(f'{kind}: wall-clock timeout — stopping round')
            break

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
            optimistic_registered += 1
            logger.debug('%s search %d: %s', kind, attempted, query)
            _delay(opts)
        if result.stalled:
            break

        # --- Per-batch verification ---
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
            # Counter-based verification is the most reliable
            registered_total += min(counter_delta, batch)
            last_counter = after.counter(kind) or last_counter
            optimistic_registered -= min(counter_delta, batch)
            rlog.registered = registered_total
            zero_delta_batches = 0
            no_signal_batches = 0
        elif points_delta is not None and points_delta > 0:
            # Points-based verification
            registered_total += batch
            optimistic_registered = 0
            rlog.registered = registered_total
            zero_delta_batches = 0
            no_signal_batches = 0
            if after.progress(kind).maximum is None:
                result.notes.append('using point deltas (search counter unavailable)')
        elif (
            (counter_delta is None and points_delta is None)
            or (points_delta is not None and points_delta == 0)
        ):
            # No immediate signal from medallion. This is the KEY issue:
            # the medallion balance lags, so we don't immediately assume failure.
            #
            # Strategy: trust that the batch registered (optimistically accumulate)
            # but track how many batches we've optimistically registered. If they
            # accumulate too long without verification, do an exhaustive check.
            last_counter = after.counter(kind)
            last_points = after.points
            if points_delta == 0:
                zero_delta_batches += 1
            else:
                no_signal_batches += 1
            total_quiet = zero_delta_batches + no_signal_batches
            log.event(
                f'{kind}: batch #{total_quiet} with no immediate increment '
                f'(source={after.source}, counter_delta={counter_delta}, '
                f'points_delta={points_delta}; optimistic_accumulator={optimistic_registered})'
            )

            # After several quiet batches, do an exhaustive re-check with force refresh
            if total_quiet >= opts_mod.MAX_NO_SIGNAL_BATCHES // 3 and not stall_handled:
                _exhaustive_recheck(kind, session, opts, queries, log,
                                    last_points, last_counter, before, result,
                                    registered_total, attempted)
                # Update tracking variables after recheck
                re_after = session.status()
                re_counter_delta = _progress_delta(kind, before, last_counter, re_after)
                re_points_delta = _points_delta(last_points, re_after.points)
                if (re_counter_delta is not None and re_counter_delta > 0) or \
                   (re_points_delta is not None and re_points_delta > 0):
                    # Optimistic accumulator was right — confirm all pending searches
                    if re_counter_delta is not None and re_counter_delta > 0:
                        registered_total += min(re_counter_delta, optimistic_registered)
                        last_counter = re_after.counter(kind) or last_counter
                    elif re_points_delta is not None and re_points_delta > 0:
                        registered_total += optimistic_registered
                        last_points = re_after.points
                    optimistic_registered = 0
                    rlog.registered = registered_total
                    stall_handled = True
                    zero_delta_batches = 0
                    no_signal_batches = 0
                    result.notes.append(
                        f'optimistic batch confirmed after exhaustive check '
                        f'(+{optimistic_registered} searches verified)'
                    )
                    continue

                # Force refresh didn't help either — this may be a genuine stall.
                # Recovery burst: before giving up, wait longer + do more searches
                recovered = _try_recovery_burst(kind, session, opts, queries, log,
                                                last_points, last_counter, before)
                if recovered:
                    last_points = recovered['points']
                    last_counter = recovered['counter']
                    registered_total += recovered.get('delta', 0)
                    optimistic_registered = 0
                    rlog.registered = registered_total
                    stall_handled = True
                    zero_delta_batches = 0
                    no_signal_batches = 0
                    result.notes.append(
                        f'recovery burst: +{recovered.get("delta", 0)} searches registered'
                    )
                    continue

            if total_quiet >= opts_mod.MAX_NO_SIGNAL_BATCHES:
                result.notes.append(
                    f'stalled after exhaustive check: {total_quiet} batches without increment '
                    f'(including {optimistic_registered} optimistically-tracked searches)'
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
        optimistic_registered = 0
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


def _mobile_refresh_signal(session) -> None:
    """Mobile medallion won't render on Bing search pages.

    Navigate to bing.com home (no query) for the medallion to load, then
    back to a search page so subsequent searches keep counting.
    """
    try:
        session.driver.get('https://www.bing.com/')
        time.sleep(2.0 + random.uniform(0, 2.0))
    except Exception:
        pass


def _try_recovery_burst(
    kind: str,
    session: Session,
    opts: opts_mod.Options,
    queries: QueryGenerator,
    log: RunLog,
    last_points: int | None,
    last_counter: int | None,
    status_before: rewards.Status,
) -> dict | None:
    """When points stall, wait for Bing's rate-limit window to clear then do
    a few more searches with extra long delays.

    Returns {'points': new_balance, 'counter': new_counter, 'delta': registered}
    if any new signal appeared, else None so the outer loop keeps counting
    toward the stall threshold.
"""
    burst_count = getattr(opts_mod, 'RECOVERY_BURST_COUNT', 3)
    burst_delay = getattr(opts_mod, 'RECOVERY_BURST_DELAY', 30.0)
    logger.info(
        '%s: no-signal streak — cooling off %.0fs then %d recovery searches',
        kind, burst_delay, burst_count,
    )
    time.sleep(burst_delay)
    for _ in range(burst_count):
        query = queries.next()
        try:
            session.search(query)
        except RuntimeError as e:
            logger.warning('%s: recovery search failed: %s', kind, e)
            break
        time.sleep(random.uniform(opts.max_delay, opts.max_delay + 6.0))
    # Re-read status from the dashboard (fresh balance after cooldown).
    after = session.status(force_refresh=True)
    points_delta = _points_delta(last_points, after.points)
    counter_delta = _progress_delta(kind, status_before, last_counter, after)
    if (counter_delta is not None and counter_delta > 0):
        log.event(f'{kind}: recovery burst registered {counter_delta} searches')
        return {'points': after.points, 'counter': after.counter(kind),
                'delta': min(counter_delta, burst_count)}
    if points_delta is not None and points_delta > 0:
        log.event(f'{kind}: recovery burst registered +{points_delta} points')
        return {'points': after.points, 'counter': last_counter,
                'delta': burst_count}
    return None


def _exhaustive_recheck(  # noqa: PLR0913 - re-check requires full context
    kind: str,
    session: Session,
    opts: opts_mod.Options,
    queries: QueryGenerator,
    log: RunLog,
    last_points: int | None,
    last_counter: int | None,
    status_before: rewards.Status,
    result: RoundResult,
    registered_total: int,
    attempted: int,
) -> None:
    """Exhaustive re-check when medallion-based verification keeps showing stale balances.

    Called after MAX_NO_SIGNAL_BATCHES // 3 quiet batches. Instead of giving up,
    we:
    1. Force-refresh the medallion widget via JavaScript
    2. Wait 30 seconds for server-side balance to propagate
    3. Re-read status multiple times (force refresh)
    4. If we find any increase at all, confirm the optimistic batch
    """
    recheck_wait = getattr(opts_mod, 'RECHECK_WAIT', 30.0)
    logger.info(
        '%s: medallion appears stale -- exhaustive re-check (waiting %.0fs, '
        'force-refresh x3)',
        kind, recheck_wait,
    )
    time.sleep(recheck_wait)

    # Attempt 1: force refresh medallion on current bing.com page
    after1 = session.status(force_refresh=True)
    counter1 = _progress_delta(kind, status_before, last_counter, after1)
    points1 = _points_delta(last_points, after1.points)
    if (counter1 is not None and counter1 > 0) or (points1 is not None and points1 > 0):
        result.notes.append(
            f'exhaustive re-check: batch confirmed +{counter1 or points1} '
            f'after {recheck_wait:.0f}s wait'
        )
        log.event(
            f'{kind}: exhaustive re-check succeeded '
            f'(counter_delta={counter1}, points_delta={points1})'
        )
        return

    # Attempt 2: navigate to rewards.bing.com to read fresh balance
    if hasattr(session, 'driver'):
        try:
            session.driver.get(rewards.REWARDS_URL)
            time.sleep(4.0)
            after2 = session.status(force_refresh=True)
            counter2 = _progress_delta(kind, status_before, last_counter, after2)
            points2 = _points_delta(last_points, after2.points)
            if (counter2 is not None and counter2 > 0) or (points2 is not None and points2 > 0):
                result.notes.append(
                    f'exhaustive re-check: batch confirmed after dashboard visit '
                    f'(counter_delta={counter2}, points_delta={points2})'
                )
                log.event(
                    f'{kind}: exhaustive re-check (dashboard) succeeded '
                    f'(counter_delta={counter2}, points_delta={points2})'
                )
                # Navigate back to bing.com for continued searches
                session.driver.get('https://www.bing.com/')
                time.sleep(1.5)
                return
        except Exception as e:
            logger.debug('%s: exhaustive re-check dashboard visit failed: %s', kind, e)

    # Attempt 3: do 3 more searches with very long delays (forces Bing to recheck)
    logger.info('%s: exhaustive re-check — doing 3 additional searches with long delays', kind)
    for _ in range(3):
        query = queries.next()
        try:
            session.search(query)
        except RuntimeError:
            break
        time.sleep(random.uniform(20.0, 40.0))
    after3 = session.status(force_refresh=True)
    counter3 = _progress_delta(kind, status_before, last_counter, after3)
    points3 = _points_delta(last_points, after3.points)
    if (counter3 is not None and counter3 > 0) or (points3 is not None and points3 > 0):
        result.notes.append(
            f'exhaustive re-check: batch confirmed via additional searches '
            f'(counter_delta={counter3}, points_delta={points3})'
        )
        log.event(
            f'{kind}: exhaustive re-check (extra searches) succeeded '
            f'(counter_delta={counter3}, points_delta={points3})'
        )
        return


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
