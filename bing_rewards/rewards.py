# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Live rewards status: points balance and desktop/mobile search progress.

Verification signals, in order of reliability for a logged-in bing.com session:
1. The rewards medallion (`#rh_rwm`) embedded on every Bing search results page.
   Its `data-content` attribute is base64 JSON carrying the authoritative
   points `balance` — readable with zero extra navigation, right after a search.
2. The legacy rewards.bing.com user-status JSON API (per-card search progress),
   when the account's market still serves it.
3. A last-resort DOM scrape of the rewards page.
Every method is failure-tolerant: fields the page doesn't expose come back
None and the collector degrades to point-delta verification instead of
crashing.
"""

from __future__ import annotations

import base64
import dataclasses
import json
import logging
import re
import time

logger = logging.getLogger(__name__)

REWARDS_URL = 'https://rewards.bing.com/'
USERSTATUS_JS = """
const url = 'https://rewards.bing.com/api/userstatus?biz=REST&schema=1';
return fetch(url, { credentials: 'include' }).then(r => r.text());
"""


@dataclasses.dataclass
class Progress:
    """One search-card progress value, e.g. 12 of 30 desktop searches."""

    current: int | None = None
    maximum: int | None = None

    @property
    def complete(self) -> bool:
        return self.current is not None and self.maximum is not None and self.current >= self.maximum


@dataclasses.dataclass
class Status:
    """Snapshot of the rewards account at one point in time."""

    points: int | None = None
    desktop: Progress = dataclasses.field(default_factory=Progress)
    mobile: Progress = dataclasses.field(default_factory=Progress)
    source: str = 'none'  # 'api' | 'dom' | 'none'
    raw: dict | None = None

    def progress(self, kind: str) -> Progress:
        return self.desktop if kind == 'desktop' else self.mobile

    def counter(self, kind: str) -> int | None:
        return self.progress(kind).current


def _int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _classify(activity_type: str) -> str | None:
    t = activity_type.lower()
    if 'search' not in t:
        return None
    if 'mobile' in t or 'narrow' in t:
        return 'mobile'
    if 'desktop' in t or t in ('pcsearch', 'pc_test'):
        return 'desktop'
    return None


def parse_userstatus(payload: dict | str) -> Status:
    """Parse a rewards user-status API payload into a Status snapshot."""
    if isinstance(payload, str):
        payload = json.loads(payload)
    data = payload.get('userStatus', payload) if isinstance(payload, dict) else {}

    status = Status(source='api', raw=payload)
    status.points = _int_or_none(data.get('availablePoints'))

    for entry in data.get('dailySetProgress', []) or []:
        for day in entry.get('dailyProgress', []) or []:
            kind = _classify(str(day.get('activityType', '')))
            if kind is None:
                continue
            attrs = day.get('attributes', {}) or {}
            cur = _int_or_none(attrs.get('currentProgress'))
            mx = _int_or_none(attrs.get('maxProgress'))
            prog = status.progress(kind)
            # Keep the richest card seen for each kind.
            if mx is not None and (prog.maximum is None or mx > prog.maximum):
                setattr(status, kind, Progress(cur, mx))
            elif cur is not None and prog.current is None:
                setattr(status, kind, Progress(cur, None))
    return status


MEDALLION_SEL = '#rh_rwm[data-rewards-widget]'


def read_medallion(driver) -> Status | None:
    """Read the rewards medallion embedded in the current bing.com page.

    Returns None when the widget isn't on the page (caller tries other sources).
    """
    try:
        el = driver.find_element('css selector', MEDALLION_SEL)
        raw = el.get_attribute('data-content')
    except Exception:  # noqa: BLE001 - element-not-found variants
        return None
    if not raw:
        return None
    try:
        pad = '=' * (-len(raw) % 4)
        data = json.loads(base64.b64decode(raw + pad))
    except (ValueError, json.JSONDecodeError) as e:
        logger.debug('medallion payload unreadable: %s', e)
        return None
    status = Status(source='medallion', raw=data)
    status.points = _int_or_none(data.get('balance'))
    return status


def read_status(driver) -> Status:
    """Read the live rewards status through the browser session.

    Prefers the SERP medallion (free when already on a bing page), then the
    legacy user-status API, then a DOM scrape.
    """
    if 'bing.com' not in (driver.current_url or ''):
        driver.get('https://www.bing.com/')
        time.sleep(1.5)
    medallion = read_medallion(driver)
    if medallion is not None and medallion.points is not None:
        return medallion
    try:
        if REWARDS_URL not in (driver.current_url or ''):
            driver.get(REWARDS_URL)
            time.sleep(2.0)
        text = driver.execute_script(USERSTATUS_JS)
        if isinstance(text, dict):
            text = json.dumps(text)
        if text:
            status = parse_userstatus(text)
            if status.points is None and medallion is not None:
                status.points = medallion.points
            return status
    except Exception as e:  # noqa: BLE001 - JS/selenium failures all fall back to DOM
        logger.debug('status API unreadable (%s); falling back', e)
    if medallion is not None:
        return medallion
    return _read_status_dom(driver)


def _read_status_dom(driver) -> Status:
    """Fallback: scrape the visible rewards page numbers."""
    status = Status(source='dom')
    try:
        text = driver.find_element('css selector', '#rewardsContainer').text
    except Exception:  # noqa: BLE001
        try:
            text = driver.find_element('css selector', 'body').text
        except Exception:  # noqa: BLE001
            return status

    m = re.search(r'([\d,]{2,})\s*Points', text)
    if m:
        status.points = _int_or_none(m.group(1).replace(',', ''))

    for line in text.splitlines():
        m = re.search(r'(\d+)\s*/\s*(\d+)', line)
        if not m:
            continue
        prog = Progress(int(m.group(1)), int(m.group(2)))
        low = line.lower()
        if 'mobile' in low:
            status.mobile = prog
        elif 'search' in low or 'desktop' in low or 'pc' in low:
            status.desktop = prog
    status.source = 'dom' if status.points is not None else 'none'
    return status
