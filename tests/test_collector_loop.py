# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Regression tests for the collector loop — guard against infinite loops.

The 'no verification signal' branch used to have no exit: a Bing page that
returned neither search-counter nor point-delta made ``run_round`` spin
forever. These tests pin the fix by driving a mock session that always
returns ``Status(source='none')`` and asserting the round terminates.
"""

import unittest
from pathlib import Path

from bing_rewards import options as opts_mod
from bing_rewards.collector import RealSession, run_round
from bing_rewards import rewards, runlog


class _NullSession:
    """Session whose every status read returns no numeric signal at all."""

    name = 'null-desktop'

    def __init__(self, kind='desktop'):
        self.kind = kind

    def signed_in(self) -> tuple[bool, str]:
        return True, 'null session (always signed in)'

    def status(self) -> rewards.Status:
        return rewards.Status(source='none')

    def search(self, query: str) -> None:
        pass  # no-op: do not touch the network


class NoSignalTerminatesTest(unittest.TestCase):
    """run_round must terminate even when the page never yields a signal."""

    def _run(self, kind='desktop', target=10):
        opts = opts_mod.Options(
            desktop=(kind == 'desktop'),
            mobile=(kind == 'mobile'),
            max_delay=0.0,
            min_delay=0.0,
            runs_dir=Path('/tmp/bing-rewards-test'),
            screenshots_dir=None,
        )
        opts.desktop_count = target
        opts.mobile_count = target
        runs_dir = Path('/tmp/bing-rewards-test')
        runs_dir.mkdir(parents=True, exist_ok=True)
        log = runlog.RunLog(path=runs_dir / 'test.json', day='2026-01-01')
        session = _NullSession(kind)
        result = run_round(kind, session, opts, log)
        return result

    def test_no_signal_stalls_gracefully(self):
        result = self._run(target=10)
        self.assertFalse(result.complete, 'round should NOT be marked complete')
        self.assertTrue(result.stalled, 'round should be marked stalled')
        self.assertIn('stalled', ' | '.join(result.notes))

    def test_no_signal_bounded_by_max_no_signal(self):
        # Even with an absurdly high target, the round must terminate within
        # MAX_NO_SIGNAL_BATCHES consecutive unverifiable batches.
        result = self._run(target=30)
        max_searches = opts_mod.BATCH_SIZE * opts_mod.MAX_NO_SIGNAL_BATCHES
        self.assertLessEqual(result.attempted, max_searches)

    def test_normal_mock_completes(self):
        """Sanity check: a cooperative page still reaches the target."""
        from bing_rewards import mock as mock_mod

        opts = opts_mod.Options(
            desktop=True,
            mobile=False,
            max_delay=0.0,
            min_delay=0.0,
            runs_dir=Path('/tmp/bing-rewards-test'),
            screenshots_dir=None,
        )
        opts.desktop_count = 30
        runs_dir = Path('/tmp/bing-rewards-test')
        runs_dir.mkdir(parents=True, exist_ok=True)
        log = runlog.RunLog(path=runs_dir / 'test-complete.json', day='2026-01-01')
        session = mock_mod.MockSession('desktop', shared={'desktop': 0, 'mobile': 0, 'points': 0})
        result = run_round('desktop', session, opts, log)
        self.assertTrue(result.complete)


if __name__ == '__main__':
    unittest.main()
