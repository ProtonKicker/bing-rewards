# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Mock rewards account for --dry-run: exercises the whole loop, burns nothing.

Simulates signed-in state, a points balance, desktop/mobile search-card
progress, and (optionally) a mid-round stall so the retry/stall detection path
is tested too.
"""

from __future__ import annotations

import logging

from bing_rewards import rewards

logger = logging.getLogger(__name__)

DESKTOP_MAX = 30
MOBILE_MAX = 10
POINTS_PER_SEARCH = 1

DEFAULT_STATE = {'desktop': 0, 'mobile': 0, 'points': 1250}


class MockSession:
    """A fake collector Session over a shared in-memory account state."""

    def __init__(
        self,
        kind: str,
        *,
        shared: dict | None = None,
        stall_after: int | None = None,
        signed_in: bool = True,
    ):
        self.name = f'mock-{kind}'
        self.kind = kind
        # Share the live dict so both rounds see the same account.
        self._state = shared if shared is not None else dict(DEFAULT_STATE)
        self._stall_after = stall_after
        self._signed_in = signed_in
        self._searches_this_round = 0

    def signed_in(self) -> tuple[bool, str]:
        if self._signed_in:
            return True, 'mock session (signed in)'
        return False, 'mock session configured to be signed out'

    def status(self) -> rewards.Status:
        status = rewards.Status(source='api', points=self._state['points'])
        status.desktop = rewards.Progress(self._state['desktop'], DESKTOP_MAX)
        status.mobile = rewards.Progress(self._state['mobile'], MOBILE_MAX)
        return status

    def search(self, query: str) -> None:
        self._searches_this_round += 1
        if self._stall_after is not None and self._searches_this_round > self._stall_after:
            logger.debug('mock: stalled on %r', query)
            return
        key = 'desktop' if self.kind == 'desktop' else 'mobile'
        maximum = DESKTOP_MAX if self.kind == 'desktop' else MOBILE_MAX
        self._state[key] = min(self._state[key] + 1, maximum)
        self._state['points'] += POINTS_PER_SEARCH
