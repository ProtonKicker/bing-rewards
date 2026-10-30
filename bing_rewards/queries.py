# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Human-ish search queries built from the bundled keyword corpus.

Strategy: produce queries that look like what a real person would type --
simple keyword lookups ("weather today"), natural questions ("what causes
aurora borealis"), occasional local/news/comparison searches.  Uniform
queries get flagged; we intersperse patterns.
"""

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
    """Yields varied, human-like queries; reshuffles when exhausted."""

    # Query patterns weighted toward simple lookups (most natural), with
    # occasional questions, comparisons, and local/news queries.
    PATS = (
        '{word}',                               # simple keyword (most common)
        '{word}',                               # weighted toward simple
        '{word}',
        '{word}',
        '{word}',
        '{word}',                               # 6 out of 16 = simple lookup
        'what is {word}',                       # knowledge lookup
        'how is {word}',                        # knowledge lookup
        '{word} near me',                       # local search
        '{word} today',                         # trending/news
        '{word} news',                          # news
        '{word} 2026',                          # year-specific
        'best {word}',                          # comparison
        'why is {word}',                        # question
        '{word} vs',                            # comparison starter
        '{word} explained',                     # explanation
    )

    def __init__(self) -> None:
        self._words: list[str] = []
        self._used: set[str] = set()

    def next(self) -> str:
        if not self._words:
            self._words = load_keywords()
            self._used.clear()
        base = self._words.pop()
        pat = random.choice(self.PATS)
        query = pat.format(word=base)
        # Avoid repeats within a run when possible.
        tries = 0
        while query in self._used and tries < MAX_REPEAT_TRIES and self._words:
            base = self._words.pop()
            pat = random.choice(self.PATS)
            query = pat.format(word=base)
            tries += 1
        self._used.add(query)
        return query

    def fresh(self) -> None:
        """Force a new shuffled pool — used before a retry round."""
        self._words = []


def search_url(query: str, base: str) -> str:
    return base + quote_plus(query)
