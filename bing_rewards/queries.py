# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Human-ish search queries built from the bundled keyword corpus."""

from __future__ import annotations

import random
from importlib import resources
from urllib.parse import quote_plus

MAX_REPEAT_TRIES = 5


def load_keywords() -> list[str]:
    """Read the full keyword corpus once, shuffled."""
    word_data = resources.files('bing_rewards').joinpath('data', 'keywords.txt')
    with resources.as_file(word_data) as p, p.open(encoding='utf-8') as fh:
        words = [line.strip() for line in fh if line.strip()]
    random.shuffle(words)
    return words


class QueryGenerator:
    """Yields varied queries; reshuffles when exhausted so retries differ."""

    PREFIXES = ('', '', '', 'what is ', 'best ', 'how does ', 'why ')
    SUFFIXES = ('', '', '', 'today', 'near me', 'explained')

    def __init__(self) -> None:
        self._words: list[str] = []
        self._used: set[str] = set()

    def next(self) -> str:
        if not self._words:
            self._words = load_keywords()
            self._used.clear()
        base = self._words.pop()
        query = f'{random.choice(self.PREFIXES)}{base} {random.choice(self.SUFFIXES)}'.strip()
        # Avoid repeats within a run when possible.
        tries = 0
        while query in self._used and tries < MAX_REPEAT_TRIES and self._words:
            base = self._words.pop()
            query = f'{random.choice(self.PREFIXES)}{base} {random.choice(self.SUFFIXES)}'.strip()
            tries += 1
        self._used.add(query)
        return query

    def fresh(self) -> None:
        """Force a new shuffled pool — used before a retry round."""
        self._words = []


def search_url(query: str, base: str) -> str:
    return base + quote_plus(query)
