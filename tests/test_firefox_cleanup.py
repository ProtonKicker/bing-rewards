# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Unit tests for temp-clone cleanup (cleanup_orphan_clones)."""

import os
import time
import unittest

from bing_rewards.firefox import _LIVE_CLONES, cleanup_orphan_clones


def _touch(path, age_seconds):
    t = time.time() - age_seconds
    os.utime(path, (t, t))


class OrphanCleanupTest(unittest.TestCase):
    def test_orphan_cleanup(self):
        import tempfile
        from pathlib import Path

        root = Path(tempfile.mkdtemp(prefix="cleanup-test-"))
        old = root / "bing-rewards-profile-old"
        fresh = root / "bing-rewards-profile-fresh"
        mine = root / "bing-rewards-profile-mine"
        for d in (old, fresh, mine):
            d.mkdir()
        _touch(old, 7200)      # 2h old -> orphan, should be removed
        _touch(fresh, 60)      # fresh -> concurrent live sibling, keep
        _touch(mine, 7200)     # owned by this process, keep even though old
        _LIVE_CLONES.add(mine)
        try:
            removed = cleanup_orphan_clones(min_age_seconds=900, tmp_root=root)
            self.assertEqual(removed, 1)
            self.assertFalse(old.exists())
            self.assertTrue(fresh.exists())
            self.assertTrue(mine.exists())
        finally:
            _LIVE_CLONES.discard(mine)

    def test_non_clone_dirs_untouched(self):
        import tempfile
        from pathlib import Path

        root = Path(tempfile.mkdtemp(prefix="cleanup-test-"))
        unrelated = root / "not-a-clone"
        unrelated.mkdir()
        _touch(unrelated, 7200)
        self.assertEqual(
            cleanup_orphan_clones(min_age_seconds=900, tmp_root=root), 0
        )
        self.assertTrue(unrelated.exists())


if __name__ == "__main__":
    unittest.main()
