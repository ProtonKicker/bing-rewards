# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Per-day JSON run log making repeated runs idempotent."""

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class RoundLog:
    target: int | None = None
    registered: int = 0
    attempted: int = 0
    wasted: int = 0
    complete: bool = False
    stalled: bool = False


@dataclasses.dataclass
class RunLog:
    path: Path
    day: str
    points_before: int | None = None
    points_after: int | None = None
    rounds: dict[str, RoundLog] = dataclasses.field(
        default_factory=lambda: {'desktop': RoundLog(), 'mobile': RoundLog()}
    )
    events: list[str] = dataclasses.field(default_factory=list)

    def round(self, kind: str) -> RoundLog:
        return self.rounds[kind]

    def event(self, text: str) -> None:
        self.events.append(text)

    def save(self) -> None:
        payload = dataclasses.asdict(self)
        payload.pop('path')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(payload, indent=2, default=str))
        tmp.replace(self.path)


def today_log_path(runs_dir: Path) -> Path:
    return runs_dir / f'{date.today().isoformat()}.json'


def load_or_start(runs_dir: Path) -> RunLog:
    """Load today's log if present so a second run skips finished rounds."""
    path = today_log_path(runs_dir)
    day = path.stem
    if path.is_file():
        try:
            data = json.loads(path.read_text())
            rounds = {
                kind: RoundLog(**{k: v for k, v in r.items() if k in RoundLog.__dataclass_fields__})
                for kind, r in (data.get('rounds') or {}).items()
                if kind in ('desktop', 'mobile')
            }
            for kind in ('desktop', 'mobile'):
                rounds.setdefault(kind, RoundLog())
            log = RunLog(
                path=path,
                day=day,
                points_before=data.get('points_before'),
                points_after=data.get('points_after'),
                rounds=rounds,
                events=data.get('events') or [],
            )
            logger.info('resuming from existing run log %s', path)
            return log
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning('run log %s unreadable (%s); starting fresh', path, e)
    return RunLog(path=path, day=day)
