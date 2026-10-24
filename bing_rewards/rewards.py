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

Enhanced: explicit WebDriverWaits for the medallion widget, and a dedicated
dashboard-DOM reader for Daily Set activities and live progress when the
medallion's per-card data is absent.
"""

from __future__ import annotations

import base64
import dataclasses
import json
import logging
import re
import time

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

REWARDS_URL = 'https://rewards.bing.com/'

# Timeout (seconds) for waiting for the medallion to render after a page load.
MEDALLION_TIMEOUT = 8

# Older user-status endpoint (still works in some markets).
USERSTATUS_JS = """
const url = 'https://rewards.bing.com/api/userstatus?biz=REST&schema=1';
return fetch(url, { credentials: 'include' }).then(r => r.text());
"""

# Rewards dashboard v2 API: more reliable in markets where userstatus is
# deprecated. Returns daily-set progress cards with activityType /
# currentProgress / maxProgress.
DASHBOARD_JS = """
const url = 'https://rewards.bing.com/api/dashboard?deskdebug=1';
return fetch(url, { credentials: 'include' }).then(r => r.text());
"""

# DailySet API — alternative endpoint used by the Bing mobile app.
DAILYSET_JS = """
const url = 'https://rewards.bing.com/api/dailyset';
return fetch(url, { credentials: 'include' }).then(r => r.text());
"""


@dataclasses.dataclass
class Activity:
    """A clickable on-rewards-page activity (Daily Set, quiz, poll, etc.)."""

    url: str
    title: str
    points: int | None = None
    completed: bool = False


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
    activities: list[Activity] = dataclasses.field(default_factory=list)

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


def wait_for_medallion(driver, timeout: float = MEDALLION_TIMEOUT):
    """Wait up to *timeout* seconds for the rewards medallion to render.

    The medallion widget loads asynchronously via Bing's rewards.js — it may
    not be in the DOM immediately after a navigation. Returns the element or
    None if it never appeared.
    """
    try:
        el = WebDriverWait(driver, timeout, poll_frequency=0.5).until(
            lambda d: d.find_elements('css selector', MEDALLION_SEL) or None
        )
        return el
    except (TimeoutException, NoSuchElementException, StaleElementReferenceException):
        return None


def read_medallion(driver) -> Status | None:
    """Read the rewards medallion embedded in the current bing.com page.

    First waits up to MEDALLION_TIMEOUT for the widget to appear on the page,
    so callers right after a search navigation still get a result.
    Returns None when the widget isn't on the page (caller tries other sources).
    """
    try:
        els = driver.find_elements('css selector', MEDALLION_SEL)
        if not els:
            els = wait_for_medallion(driver)
        if not els:
            return None
        el = els[0]
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
    # The medallion sometimes carries richer quota data under `cards`.
    for card in (data.get('cards') or []) if isinstance(data, dict) else []:
        ctype = str(card.get('cardType', '')).lower()
        if 'search' in ctype:
            prog = Progress(
                _int_or_none(card.get('progress')),
                _int_or_none(card.get('max')),
            )
            kind = 'mobile' if 'mobile' in ctype or 'narrow' in ctype else 'desktop'
            if prog.maximum and (status.progress(kind).maximum is None):
                setattr(status, kind, prog)
    return status


def read_status(driver) -> Status:
    """Read the live rewards status through the browser session.

    Primary source: the rewards.bing.com dashboard DOM — it renders the true
    current balance (bing.com's medallion widget often shows a cached balance
    that does not advance between searches, making it unreliable for
    per-batch verification).

    Flow:
    1. Dashboard DOM scrape — authoritative balance + Daily Set activities.
    2. Rewards APIs (userstatus, dashboard, dailyset) — carry per-card search
       progress; merged into the dashboard result if they add data.
    3. bing.com medallion — used only for per-card progress the dashboard omits.
    4. Raw body scrape as a last resort.
    """
    # Try the rewards APIs first for per-card progress (cheap — no navigation).
    api_status = _try_all_status_apis(driver)

    # Always read the dashboard DOM for the authoritative balance.
    dash = _read_status_from_dashboard(driver)

    # Merge API per-card progress into the dashboard result (keep the
    # dashboard's balance, which is always fresher than the API's).
    if api_status is not None and dash.points is not None:
        if dash.desktop.maximum is None and api_status.desktop.maximum is not None:
            dash.desktop = api_status.desktop
        if dash.mobile.maximum is None and api_status.mobile.maximum is not None:
            dash.mobile = api_status.mobile
        dash.source = 'api+dom'
    elif api_status is not None and dash.points is None:
        # Dashboard failed entirely; trust the API if it has something.
        api_status.source = 'api'
        return api_status

    if dash.points is not None:
        return dash

    # If dashboard DOM missed the balance (unusual), fall back to the medallion
    # embedded in the bing.com page.
    on_bing = 'bing.com' in (driver.current_url or '')
    if not on_bing:
        driver.get('https://www.bing.com/')
        time.sleep(1.5)
    medallion = read_medallion(driver)
    if medallion is not None and medallion.points is not None:
        if dash.activities:
            medallion.activities = dash.activities
        return medallion

    if medallion is not None:
        return medallion
    return dash


def _try_all_status_apis(driver) -> Status | None:
    """Try each rewards API endpoint in order; return the first that succeeds.

    Validates the response is real JSON with expected fields — skips
    error pages that Bing sometimes returns instead of the rewards data.
    """
    # Make sure we're on a bing.com domain for the API call (CORS).
    if 'bing.com' not in (driver.current_url or ''):
        driver.get(REWARDS_URL)
        time.sleep(2.0)

    api_scripts = [('userstatus', USERSTATUS_JS), ('dashboard', DASHBOARD_JS), ('dailyset', DAILYSET_JS)]
    for name, script in api_scripts:
        try:
            text = driver.execute_script(script)
            if isinstance(text, dict):
                text = json.dumps(text)
            if not text:
                continue
            # Bing sometimes returns an HTML error page (e.g. "Rewards Error")
            # instead of JSON — detect and skip those instead of crashing.
            stripped = text.strip()
            if stripped.startswith('<') or stripped.startswith('<!'):
                logger.debug('%s API returned HTML (error page), skipping', name)
                continue
            data = json.loads(stripped)
            # Quick sanity: valid rewards responses are objects, not arrays
            # or bare strings.
            if not isinstance(data, dict):
                continue
            status = parse_userstatus(data)
            # Only accept if we got at least points or some progress info.
            if status.points is not None or status.desktop.maximum is not None or status.mobile.maximum is not None:
                logger.debug('status OK from %s API (source=%s)', name, status.source)
                # Merge in medallion points as fallback (more reliable balance).
                if status.points is None:
                    m = read_medallion(driver)
                    if m is not None:
                        status.points = m.points
                return status
            logger.debug('%s API returned sterile data, trying next endpoint', name)
        except (json.JSONDecodeError, Exception) as e:
            logger.debug('%s API failed (%s), trying next endpoint', name, e)
            continue
    return None


def _read_status_from_dashboard(driver) -> Status:
    """Scrape points + per-card progress directly from rewards.bing.com DOM.

    Called when both the medallion and APIs failed, or as a cross-check. The
    rewards.bing.com page is a SPA that renders the balance as a large numeric
    value — we hunt for the largest standalone number (1,000+) on the page.
    Also scans for uncompleted Daily Set activities.
    """
    status = Status(source='dom')
    try:
        driver.get(REWARDS_URL)
        WebDriverWait(driver, 10, poll_frequency=0.5).until(
            lambda d: 'dashboard' in d.current_url.lower() or
                      d.find_elements('css selector', '[class*="gamification"]')
        )
        time.sleep(1.5)
    except Exception:  # noqa: BLE001
        logger.debug('dashboard page load timed out')
        return status

    # --- Parse all text with embedded numbers ---
    try:
        page_text = driver.find_element('css selector', 'body').text
    except Exception:
        page_text = ''

    # Find balance: the first large standalone number (>= 1000) on the page,
    # typically "4,898" or "4,898 points". Skip progress sub-quotas like 3,500.
    for line in page_text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.search(r'\b([\d,]{4,})\b', line)
        if m:
            value = _int_or_none(m.group(1).replace(',', ''))
            if value and value >= 1000:
                status.points = value
                break

    # --- Parse progress counters ---
    # Two layouts seen in the wild:
    #   (a) "Desktop searches 5/30" — all on one line.
    #   (b) "Bing search" / "25/25" — number on the line AFTER the label.
    # We capture the latter by tracking the previous non-empty line.
    prev_line = ''
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
    for idx, line in enumerate(lines):
        m_pat = re.search(r'(\d[\d,]*)\s*/\s*(\d[\d,]*)', line)
        if not m_pat:
            prev_line = line
            continue
        cur = _int_or_none(m_pat.group(1).replace(',', ''))
        mx = _int_or_none(m_pat.group(2).replace(',', ''))
        if cur is None or mx is None:
            prev_line = line
            continue
        # Skip sub-quotas like "Progress towards Silver • Points to go: 375" by
        # only accepting ratios where the denominator is a round 5, 10, 20, 25, 30 ...
        # (Microsoft's quotas) OR the ratio is close to complete.
        low = line.lower() + ' ' + prev_line.lower()
        prog = Progress(cur, mx)
        if 'mobile' in low or 'phone' in low:
            status.mobile = prog
        elif 'search' in low or 'desktop' in low or 'pc' in low or 'bing' in low:
            status.desktop = prog
        elif status.desktop.current is None and mx in (10, 15, 20, 25, 30, 50, 100, 150):
            # Fallback: if a line's label is missing but the denominator is a
            # plausible Bing quota, tag it as desktop search (the most common card).
            status.desktop = prog
        prev_line = line

    # --- Parse Daily Set activities ---
    status.activities = _parse_activities_from_dom(driver)
    status.source = 'dom' if status.points is not None else 'none'
    return status


def _parse_activities_from_dom(driver) -> list[Activity]:
    """Find uncompleted clickable activities on the rewards dashboard.

    Returns a list of Activity with the target URL for each uncompleted item.
    Activities are identified as cards/links with a "+" points badge and an
    "unchecked" or "not-completed" state indicator.
    """
    activities: list[Activity] = []
    try:
        # Activity cards typically have a clickable <a> wrapping an earn button.
        # Look for elements that show uncompleted offers/quizzes/polls.
        cards = driver.find_elements(
            'css selector',
            '[data-context*="daily"] a, [data-bi-name*="earn"] a, '
            '.daily-set a, .open-check a, a[href*="/dashboard"]',
        )
        for card in cards[:20]:  # cap to avoid runaway iteration
            try:
                href = card.get_attribute('href') or ''
                card_text = (card.text or '').strip()
                if not href or not card_text or len(card_text) < 3:
                    continue
                # Check if completed by looking for "checked" indicator near this card.
                # Completed items usually contain a checkmark SVG or "✓" text.
                parent = card
                for _ in range(3):
                    try:
                        parent = parent.find_element('xpath', '..')
                        parent_html = parent.get_attribute('outerHTML') or ''
                        if '✓' in parent_html or 'checked' in parent_html.lower() or 'completed' in parent_html.lower():
                            break
                    except Exception:
                        break
                else:
                    parent_html = ''
                completed = '✓' in parent_html or 'checked' in parent_html.lower()

                # Extract points value (e.g. "+10", "10 pts", "30").
                points_match = re.search(r'\+?\s*(\d+)\s*(pts|points)?', card_text, re.IGNORECASE)
                points = _int_or_none(points_match.group(1)) if points_match else None

                activities.append(
                    Activity(url=href, title=card_text[:60], points=points, completed=completed)
                )
            except (StaleElementReferenceException, NoSuchElementException):
                continue
            except Exception as e:
                logger.debug('activity card parse error: %s', e)
                continue
    except Exception as e:
        logger.debug('activity parse failed: %s', e)
    return activities


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
