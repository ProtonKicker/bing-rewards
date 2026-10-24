# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Entrypoint: one command runs the full closed-loop daily collection."""

from __future__ import annotations

import logging
import shutil
from typing import TYPE_CHECKING

from bing_rewards import options as opts_mod
from bing_rewards.collector import RealSession, RoundResult, run_round
from bing_rewards.daily_set import DailySetResult, run_daily_set
from bing_rewards.firefox import (
    clone_profile,
    find_profile_directory,
    firefox_is_running,
    quit_driver,
    start_driver,
)
from bing_rewards.mock import MockSession
from bing_rewards.runlog import load_or_start
from bing_rewards.screenshots import Shutter

if TYPE_CHECKING:
    from bing_rewards.runlog import RunLog

logger = logging.getLogger('bing_rewards')

VERDICT_COLORS = {'SUCCESS': '🏆', 'PARTIAL': '⚠️ ', 'FAIL': '❌'}


def main(argv: list[str] | None = None) -> int:
    opts = opts_mod.parse_args(argv)
    logging.basicConfig(
        level=(logging.DEBUG if opts.verbose else logging.INFO),
        format='%(asctime)s %(levelname)s %(message)s',
    )
    if opts.dry_run:
        # Keep mock logs out of the real idempotency record.
        opts.runs_dir = opts.runs_dir / 'dry'
    log = load_or_start(opts.runs_dir)
    shutter = Shutter(None if opts.dry_run else opts.screenshots_dir)

    daily_set_result = None
    results = _run_dry(opts, log) if opts.dry_run else _run_real(opts, log, shutter)

    # In real mode, run Daily Set completion after search rounds
    # (uses the last active driver session if possible).
    if not opts.dry_run and results:
        # Pick the last driver that was active — search rounds already quit
        # their drivers, so we need a fresh session.
        last_round = results[-1]
        if last_round.signed_in:
            daily_set_result = _run_daily_set_session(opts, log, shutter)

    log.save()
    return _report(log, results, daily_set_result)


def _rounds(opts: opts_mod.Options) -> list[str]:
    return [k for k, enabled in (('desktop', opts.desktop), ('mobile', opts.mobile)) if enabled]


def _run_real(opts: opts_mod.Options, log: RunLog, shutter: Shutter) -> list[RoundResult]:
    results: list[RoundResult] = []
    profile_src = find_profile_directory(opts.profile_name)
    if firefox_is_running():
        logger.warning(
            'Firefox is currently running — the profile clone may lag behind its '
            'newest cookies. Quit Firefox if the signed-in check fails.'
        )
    logger.info('cloning profile %s to a temp directory', profile_src)
    cloned = clone_profile(profile_src)
    try:
        for kind in _rounds(opts):
            mobile_ua = opts_mod.MOBILE_AGENT if kind == 'mobile' else None
            desktop_ua = opts_mod.DESKTOP_AGENT if kind == 'desktop' else None
            logger.info('starting Firefox for the %s round', kind)
            driver = start_driver(
                cloned,
                mobile_user_agent=mobile_ua,
                desktop_user_agent=desktop_ua,
                options=opts,
            )
            try:
                session = RealSession(driver, kind)
                shutter.capture(f'{kind}-launched', session)
                result = run_round(kind, session, opts, log, shutter)
                results.append(result)
                if not result.signed_in:
                    log.event('signed-out detected — aborting all rounds')
                    shutter.capture('signed-out', session)
                    break
            finally:
                quit_driver(driver)
    finally:
        shutil.rmtree(cloned.parent, ignore_errors=True)
    return results


def _run_daily_set_session(
    opts: opts_mod.Options, log: RunLog, shutter: Shutter
) -> DailySetResult | None:
    """Launch a fresh Firefox session just for Daily Set completion.

    Daily Set pages use desktop UA; we don't need a mobile viewport. Returns
    None if the session cannot even sign in.
    """
    profile_src = find_profile_directory(opts.profile_name)
    cloned = clone_profile(profile_src)
    driver = None
    try:
        logger.info('starting Firefox for Daily Set round')
        driver = start_driver(
            cloned,
            desktop_user_agent=opts_mod.DESKTOP_AGENT,
            options=opts,
        )
        session = RealSession(driver, 'desktop')
        ok, detail = session.signed_in()
        if not ok:
            log.event(f'Daily Set: NOT signed in ({detail}) — aborting')
            return None
        result = run_daily_set(driver)
        log.event(f'Daily Set: {result.summary()}')
        return result
    except Exception as e:  # noqa: BLE001
        logger.warning('daily-set run failed: %s', e)
        log.event(f'Daily Set: failed — {e}')
        return None
    finally:
        if driver:
            quit_driver(driver)
        shutil.rmtree(cloned.parent, ignore_errors=True)


def _run_dry(opts: opts_mod.Options, log: RunLog) -> list[RoundResult]:
    print('*** DRY RUN — no real searches, simulated rewards account ***')
    opts.min_delay = 0.0  # a mock run should finish in seconds
    opts.max_delay = 0.0
    shared = {'desktop': 0, 'mobile': 0, 'points': 1250}
    results: list[RoundResult] = []
    for kind in _rounds(opts):
        session = MockSession(kind, shared=shared, stall_after=opts.mock_stall_after)
        results.append(run_round(kind, session, opts, log))
    return results


def _report(
    log: RunLog, results: list[RoundResult], daily_set_result: DailySetResult | None = None
) -> int:
    verdict, reasons = _verdict(results)
    print()
    print('=' * 58)
    print(f'  BING REWARDS RUN REPORT — {log.day}  {VERDICT_COLORS[verdict]} {verdict}')
    print('=' * 58)
    points_line = f'  points: {log.points_before} -> {log.points_after}'
    if None not in (log.points_before, log.points_after):
        delta = log.points_after - log.points_before
        points_line += f'  ({delta:+d})'
    print(points_line)
    for r in results:
        if r.skipped_reason:
            state = f'skipped: {r.skipped_reason}'
        elif not r.signed_in:
            state = 'NOT SIGNED IN'
        else:
            tag = ' [COMPLETE]' if r.complete else ' [STALL]' if r.stalled else ''
            state = f'attempted {r.attempted}, registered {r.registered}, wasted {r.wasted}{tag}'
        print(f'  {r.kind:<8}: {state}')
    if daily_set_result is not None:
        pts_str = ''
        if daily_set_result.points_earned is not None:
            pts_str = f'  (~{daily_set_result.points_earned:+d} pts)'
        print(
            f'  dailySet: {daily_set_result.cards_clicked}/'
            f'{daily_set_result.cards_found} clicked, '
            f'{daily_set_result.cards_skipped} skipped{pts_str}'
        )
    for note in _all_notes(log, results):
        print(f'    • {note}')
    print('-' * 58)
    for reason in reasons:
        print(f'  reason: {reason}')
    print(f'  run log: {log.path}')
    print('=' * 58)
    return {'SUCCESS': 0, 'PARTIAL': 1, 'FAIL': 2}[verdict]


def _all_notes(log: RunLog, results: list[RoundResult]) -> list[str]:
    notes = [n for r in results for n in r.notes]
    notes += [e for e in log.events if 'stall' in e or 'NOT signed' in e or 'retrying' in e]
    return sorted(set(notes))


def _verdict(results: list[RoundResult]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if not results:
        return 'FAIL', ['no rounds were run']
    if any(not r.signed_in for r in results):
        reasons.append('session was not signed in to Bing — searches were not attempted')
        return 'FAIL', reasons
    registered = sum(r.registered for r in results)
    attempted = sum(r.attempted for r in results)
    complete = [r.kind for r in results if r.complete and not r.skipped_reason]
    stalled = [r.kind for r in results if r.stalled]
    skipped = [r.kind for r in results if r.skipped_reason]
    if len(skipped) == len(results):
        return 'SUCCESS', [f'all rounds already complete today ({", ".join(skipped)})']
    if registered == 0:
        reasons.append(f'{attempted} searches registered nothing — verification failed')
        return 'FAIL', reasons
    if complete and not stalled:
        reasons.append(f'all requested rounds completed ({", ".join(complete + skipped)})')
        return 'SUCCESS', reasons
    if stalled:
        reasons.append(f'points stopped registering in: {", ".join(stalled)}')
    if complete:
        reasons.append(f'completed: {", ".join(complete)}')
    reasons.append(f'registered {registered} of {attempted} attempted searches')
    return 'PARTIAL', reasons
