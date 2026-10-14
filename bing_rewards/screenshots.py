# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Stage screenshots. Window-scoped via the WebDriver when available (no
personal desktop content leaks into committed evidence); macOS screencapture
as fallback. Never fatal — evidence, not function."""

from __future__ import annotations

import logging
import shutil
import subprocess
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class Shutter:
    def __init__(self, outdir: Path | None):
        self.outdir = outdir
        self.has_screencapture = shutil.which('screencapture') is not None

    def capture(self, stage: str, session=None) -> Path | None:
        if self.outdir is None:
            return None
        self.outdir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%H%M%S')
        target = self.outdir / f'{stamp}-{stage}.png'
        shot = getattr(session, 'take_screenshot', None)
        if shot is not None and shot(str(target)):
            logger.info('screenshot: %s', target)
            return target
        if not self.has_screencapture:
            return None
        result = subprocess.run(
            ['screencapture', '-x', str(target)], capture_output=True, check=False
        )
        if result.returncode != 0 or not target.exists():
            logger.warning('screenshot %r failed: %s', stage, result.stderr.decode().strip())
            return None
        logger.info('screenshot: %s', target)
        return target
