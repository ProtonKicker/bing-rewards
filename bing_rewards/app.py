# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Entrypoint: one command runs the full closed-loop daily collection."""

from __future__ import annotations

import logging
import shutil
import time
from typing import TYPE_CHECKING

from bing_rewards import options as opts_mod
from bing_rewards.collector import RealSession, RoundResult, run_round
from bing_rewards.bing_news import BingNewsResult, run_bing_news
from bing_rewards.daily_set import DailySetResult, run_daily_set
from bing_rewards.outlook import OutlookResult, run_outlook_emails
from bing_rewards.firefox import (
    clone_profile,
    find_profile_directory,
    firefox_is_running,
    kill_firefox_pids,
    quit_driver,
    quit_firefox,
    running_firefox_pids,
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
    bing_news_result = None
    outlook_result = None
    pre_existing_pids: set[int] = set()
    if opts.dry_run:
        results = _run_dry(opts, log)
    else:
        results, pre_existing_pids = _run_real(opts, log, shutter)

    # In real mode, run Daily Set completion after search rounds
    # (uses the last active driver session if possible).
    if not opts.dry_run and results:
        # Pick the last driver that was active — search rounds already quit
        # their drivers, so we need a fresh session.
        last_round = results[-1]
        if last_round.signed_in:
            daily_set_result = _run_daily_set_session(opts, log, shutter)
            bing_news_result = _run_bing_news_session(opts, log, shutter)
            outlook_result = _run_outlook_session(opts, log, shutter)

    # Final cleanup: if the script launched Firefox (no user Firefox at start),
    # make sure it is quit now.
    if not pre_existing_pids and firefox_is_running():
        logger.info('Final cleanup: quitting Firefox launched by script')
        try:
            quit_firefox()
        except Exception as e:
            logger.debug('final quit_firefox failed: %s', e)

    log.save()
    return _report(log, results, daily_set_result, bing_news_result, outlook_result)


def _rounds(opts: opts_mod.Options) -> list[str]:
    return [k for k, enabled in (('desktop', opts.desktop), ('mobile', opts.mobile)) if enabled]


def _run_real(opts: opts_mod.Options, log: RunLog, shutter: Shutter) -> tuple[list[RoundResult], set[int]]:
    results: list[RoundResult] = []
    profile_src = find_profile_directory(opts.profile_name)
    pre_existing_pids = running_firefox_pids()
    if pre_existing_pids:
        logger.warning('Firefox is already running — profile clone may have stale cookies')
    logger.info('cloning profile %s to a temp directory', profile_src)
    cloned = clone_profile(profile_src)
    try:
        for kind in _rounds(opts):
            mobile_ua = opts_mod.MOBILE_AGENT if kind == 'mobile' else None
            desktop_ua = opts_mod.DESKTOP_AGENT if kind == 'desktop' else None
            logger.info('starting Firefox for the %s round', kind)
            round_start_pids = running_firefox_pids()
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
                # Kill only Firefox processes that appeared during this round
                # so we don't touch a user's pre-existing Firefox session.
                current_pids = running_firefox_pids()
                new_pids = current_pids - round_start_pids
                if new_pids:
                    kill_firefox_pids(new_pids)
                # Brief pause to let processes settle before next round.
                time.sleep(1.0)
    finally:
        shutil.rmtree(cloned.parent, ignore_errors=True)
    return results, pre_existing_pids


def _run_bing_news_session(
    opts: opts_mod.Options, log: RunLog, shutter: Shutter
) -> BingNewsResult | None:
    """Launch a fresh Firefox session for Bing news reading."""
    profile_src = find_profile_directory(opts.profile_name)
    cloned = clone_profile(profile_src)
    driver = None
    session_start_pids: set[int] = set()
    try:
        session_start_pids = running_firefox_pids()
        logger.info('starting Firefox for Bing News round')
        driver = start_driver(
            cloned,
            desktop_user_agent=opts_mod.DESKTOP_AGENT,
            options=opts,
        )
        session = RealSession(driver, 'desktop')
        ok, detail = session.signed_in()
        if not ok:
            log.event(f'Bing News: NOT signed in ({detail}) — aborting')
            return None
        result = run_bing_news(driver)
        log.event(f'Bing News: {result.summary()}')
        return result
    except Exception as e:  # noqa: BLE001
        logger.warning('bing news run failed: %s', e)
        log.event(f'Bing News: failed — {e}')
        return None
    finally:
        if driver:
            quit_driver(driver)
            current_pids = running_firefox_pids()
            new_pids = current_pids - session_start_pids
            if new_pids:
                kill_firefox_pids(new_pids)
            time.sleep(1.0)
        shutil.rmtree(cloned.parent, ignore_errors=True)


def _run_outlook_session(
    opts: opts_mod.Options, log: RunLog, shutter: Shutter
) -> OutlookResult | None:
    """Launch a fresh Firefox session for Outlook email reading."""
    profile_src = find_profile_directory(opts.profile_name)
    cloned = clone_profile(profile_src)
    driver = None
    session_start_pids: set[int] = set()
    try:
        session_start_pids = running_firefox_pids()
        logger.info('starting Firefox for Outlook round')
        driver = start_driver(
            cloned,
            desktop_user_agent=opts_mod.DESKTOP_AGENT,
            options=opts,
        )
        session = RealSession(driver, 'desktop')
        ok, detail = session.signed_in()
        if not ok:
            log.event(f'Outlook: NOT signed in ({detail}) — aborting')
            return None
        result = run_outlook_emails(driver)
        log.event(f'Outlook: {result.summary()}')
        return result
    except Exception as e:  # noqa: BLE001
        logger.warning('outlook run failed: %s', e)
        log.event(f'Outlook: failed — {e}')
        return None
    finally:
        if driver:
            quit_driver(driver)
            current_pids = running_firefox_pids()
            new_pids = current_pids - session_start_pids
            if new_pids:
                kill_firefox_pids(new_pids)
            time.sleep(1.0)
        shutil.rmtree(cloned.parent, ignore_errors=True)

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
    session_start_pids: set[int] = set()
    try:
        session_start_pids = running_firefox_pids()
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
            current_pids = running_firefox_pids()
            new_pids = current_pids - session_start_pids
            if new_pids:
                kill_firefox_pids(new_pids)
            time.sleep(1.0)
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
    log: RunLog, results: list[RoundResult],
    daily_set_result: DailySetResult | None = None,
    bing_news_result: BingNewsResult | None = None,
    outlook_result: OutlookResult | None = None,
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
    if bing_news_result is not None:
        print(
            f'  bingNews: {bing_news_result.articles_read}/'
            f'{bing_news_result.articles_found} read, '
            f'{bing_news_result.articles_skipped} skipped'
        )
    if outlook_result is not None:
        print(
            f'  outlook:  {outlook_result.emails_read}/'
            f'{outlook_result.emails_found} read, '
            f'{outlook_result.emails_skipped} skipped'
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
