# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Complete Daily Set activities and Explore-on-Bing cards.

The Rewards dashboard renders its clickable cards as ``<a>`` tags whose class
list contains the Tailwind tokens ``cursor-pointer`` and (usually) ``group``.
They live on the ``/earn`` page, show a short title plus a "+N" badge, and
clicking the card registers the activity server-side (you do NOT need to
interact with whatever page the href lands on — the redirecting page fires the
reward automatically).

Extra safety: we also retry the whole scan a second time because Bing SPA
sometimes renders cards lazily; the quickest possible point-burn life is for
the page to re-fire its API after a few seconds — we re-read and click on the
next pass if anything new appeared.
"""

from __future__ import annotations

import logging
import random
import re
import time

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from bing_rewards import rewards

logger = logging.getLogger(__name__)

# The activity cards on /earn use Tailwind utility classes; the distinguishing
# tokens across every layout we have seen are ``cursor-pointer`` and ``group``.
# They live on the ``/earn`` page, show a short title plus a "+N" badge, and
# clicking the card registers the activity server-side (you do NOT need to
# interact with whatever page the href lands on — the redirecting page fires the
# reward automatically).
#
# TIGHTENED: only match links within the dashboard body area (not the top nav
# bar). Navigation links ("Dashboard", "Earn", "Redeem") share the same
# CSS tokens — we must filter them out rigorously.
ACTIVITY_LINK_SELECTOR = (
    'a.cursor-pointer.group[href*="bing.com"]'  # Bing redirect activity links
    ', a[href*="/ck/a"]'   # Bing check/award redirect (most daily cards)
    ', .daily-set a[href]'  # daily-set section links
    ', .gamification a[href]'  # gamification activity links
    ', a[href*="rewards.bing.com"]'  # direct rewards links (excluding nav)
)
# Completed cards are recognised by an inline checkmark SVG or the word
# "Completed" appearing in their accessible label.
COMPLETED_TEXT = ('completed', 'claimed', 'done')
# Badge inside the card that advertises the points on offer; we use it only
# for human-readable logging.
POINTS_BADGE_RE = (r'\+\s*(\d+)\s*(pts|points)?')
# Navigation link text that we must NEVER click as an activity
NAV_LINK_TEXT = frozenset({
    'dashboard', 'earn', 'redeem', 'about', 'refer and earn',
    'rewards', 'home', 'profile', 'settings', 'help',
})


class DailySetResult:
    """Outcome of one daily-set-completion run."""

    def __init__(self) -> None:
        self.cards_found: int = 0
        self.cards_clicked: int = 0
        self.cards_skipped: int = 0
        self.points_before: int | None = None
        self.points_after: int | None = None
        self.details: list[str] = []

    @property
    def points_earned(self) -> int | None:
        if self.points_before is None or self.points_after is None:
            return None
        return self.points_after - self.points_before

    def summary(self) -> str:
        pts = f' (~{self.points_earned:+d} pts)' if self.points_earned is not None else ''
        return (
            f'Daily Set + Explore: clicked {self.cards_clicked}/{self.cards_found} '
            f'cards ({self.cards_skipped} skipped){pts}'
        )


def run_daily_set(driver) -> DailySetResult:
    """Click every uncompleted activity card on the Rewards /earn page.

    We use the medallion balance as a cheap pre/post free fluctuation gauge:
    each card gives ≥5 points, so even if a click only sometimes registers the
    balance advance dominates over noise. A no-op result is returned when the
    page is unreachable or is rendered empty (which happens right after a known
    account-level daily reset, a few local-time hours before the next round of
    activities appears).
    """
    result = DailySetResult()

    status_before = rewards.read_status(driver)
    result.points_before = status_before.points

    # Navigate to the earn page (most cards render here, not on /dashboard).
    try:
        driver.get('https://rewards.bing.com/earn')
        WebDriverWait(driver, 12, poll_frequency=0.5).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, ACTIVITY_LINK_SELECTOR) or
                      'earn' in d.current_url.lower()
        )
        # Cards render asynchronously — give the SPA a moment to populate.
        time.sleep(2.0 + random.uniform(0, 2.0))
    except (TimeoutException, Exception) as exc:
        logger.warning('could not reach /earn page (%s)', exc)
        result.details.append(f'earn page load failed: {exc}')
        _read_final_balance(driver, result)
        return result

    # Save the balance one more time on the /earn page — the medallion on this
    # page rounds to the last privacy-safe multiple sometimes, so we prefer the
    # read_status path. If both agree, great; if they differ by a few points
    # that is within error.
    medallion = rewards.read_medallion(driver)
    if medallion is not None and medallion.points is not None:
        result.points_before = medallion.points

    cards = _find_cards(driver)
    # Cap: clicking > 10 cards in one session is suspicious. Prioritize
    # URL-patterns that look like one-click daily activities (Bing search
    # redirects and reward checkuser endpoints) over media/landing pages.
    priority = []
    secondary = []
    for card in cards:
        try:
            href = (card.get_attribute('href') or '').lower()
        except Exception:
            href = ''
        if 'checkuser' in href or 'form=' in href or '/search' in href:
            priority.append(card)
        else:
            secondary.append(card)
    cards = (priority + secondary)[:10]
    result.cards_found = len(cards)
    if not cards:
        logger.info('no uncompleted card-like activity links on /earn')
        result.details.append('all cards already clicked (or none available yet)')
        _read_final_balance(driver, result)
        return result

    logger.info('found %d uncompleted card-like activity links on /earn', len(cards))
    clicked_urls: set[str] = set()
    for idx, card in enumerate(cards):
        # Dedup using href (empty-label links can still earn points).
        try:
            href = (card.get_attribute('href') or '').strip()
        except Exception:
            href = ''
        if href in clicked_urls:
            result.cards_skipped += 1
            continue
        labelled = _card_label(card) or '(no label)'
        logger.info('card %d/%d: "%s"', idx, len(cards), labelled[:60])
        ok = _try_click_card(driver, card, idx, result)
        if ok:
            clicked_urls.add(href)
        # Pause before re-reading the freshly rendered /earn page.
        time.sleep(random.uniform(2.0, 4.0))
        # Refresh our element list after every click — the SPA rewrites the DOM
        # on each navigation, so all previously found links go stale.
        try:
            # Try using browser back first — this preserves SPA state better
            # than a fresh driver.get.
            cur = (driver.current_url or '').rstrip('/')
            if cur != 'https://rewards.bing.com/earn':
                driver.execute_script('window.history.back();')
                time.sleep(2.5)
                cur2 = (driver.current_url or '').rstrip('/')
                if cur2 != 'https://rewards.bing.com/earn':
                    driver.get('https://rewards.bing.com/earn')
            WebDriverWait(driver, 10, poll_frequency=0.5).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, ACTIVITY_LINK_SELECTOR)) >= 3
            )
            time.sleep(2.0)
        except Exception:
            pass
        cards = _find_cards(driver)
        cards = [c for c in cards if (c.get_attribute('href') or '') not in clicked_urls]
        if not cards:
            break

    _read_final_balance(driver, result)
    logger.info(result.summary())
    return result


def _find_cards(driver) -> list:
    """Return clickable, uncompleted activity card links.

    Uses strict filtering to exclude navigation links (Dashboard, Earn, Redeem)
    which share the same CSS tokens as activity cards. Only links whose href
    matches known activity URL patterns are kept.
    """
    candidates: list = []
    seen_hrefs: set[str] = set()
    links = driver.find_elements(By.CSS_SELECTOR, ACTIVITY_LINK_SELECTOR)
    for link in links:
        try:
            href = (link.get_attribute('href') or '').strip()
            if not href:
                continue
            if href in seen_hrefs:
                continue
            if not _is_activity_url(href):
                continue
            # Skip navigation links by text label
            label = _card_label(link).strip().lower()
            if label in NAV_LINK_TEXT:
                logger.debug('skipping nav link: %s -> %s', label, href)
                continue
            seen_hrefs.add(href)
            # Skip cards that have already been claimed
            if _is_card_completed(link):
                continue
            candidates.append(link)
        except (StaleElementReferenceException, NoSuchElementException):
            continue
        except Exception as exc:
            logger.debug('card filter error: %s', exc)
            continue
    return candidates


def _is_activity_url(href: str) -> bool:
    """Is this href likely a direct-points Daily Set / Explore activity?

    Must be strict enough to exclude navigation links ("Dashboard", "Earn",
    "Redeem", "About", "Refer and Earn") which also live on rewards.bing.com.
    """
    if not href or href.startswith('#') or href.startswith('javascript:'):
        return False
    h = href.lower()

    # === BING REDIRECTOR (most daily cards use this) ===
    if '/ck/a' in h:
        return True
    if '/search?q=' in h or '?form=' in h:
        return True

    # === REWARDS-SPECIFIC ACTIVITY ENDPOINTS ===
    # Exclude plain navigation pages while allowing API/activity URLs
    if 'rewards.bing.com/' in h:
        path = re.sub(r'^https?://[^/]+', '', h).split('?')[0].rstrip('/')
        if path in ('', '/', '/dashboard', '/earn', '/redeem',
                     '/about', '/refer-earn', '/api'):
            return False
        if path.startswith('/api/') and '/activity' in path:
            return True
        if '?' in h:
            return True
        return False

    # === QUIZ / OFFER / REWARDS ENDPOINTS ===
    if '/rewards/' in h or '/activity/' in h or '/quiz/' in h or '/earn/' in h:
        return True
    if 'msn.com/' in h and ('rewards' in h or 'offer' in h):
        return True
    return False


def _card_label(link) -> str:
    """Human-readable label text for a card link.

    Cards render a zero-width-space separated title/description; we take the
    first text segment (before ​ or double-newline) as the title, strip any
    trailing "+N" badge, and return that.
    """
    full_text = ''
    # Best source: aria-label exposed for accessibility.
    for attr in ('aria-label', 'title'):
        try:
            value = (link.get_attribute(attr) or '').strip()
            if value and len(value) > 2:
                full_text = value
                break
        except Exception:
            pass
    if not full_text:
        for prop in ('textContent', 'innerText'):
            try:
                text = (link.get_property(prop) or '').strip()
                if text:
                    full_text = text
                    break
            except Exception:
                pass
    if not full_text:
        return ''
    # Split on zero-width space (U+200B) and take the title.
    title = full_text.split('​')[0].strip()
    # Also break on description body: lines after "+N" badge or lines that are
    # much longer than the title are usually descriptions.
    lines = [l.strip() for l in title.splitlines() if l.strip()]
    if lines:
        title = lines[0]
    # Remove trailing "+N" or "+N points" badge.
    title = re.sub(r'\+\s*\d+\s*(pts|points)?\s*$', '', title, flags=re.IGNORECASE)
    return title[:80]


def _is_card_completed(link) -> bool:
    """Best-effort: does the mark the card as completed / claimed?"""
    try:
        a11y = ''
        for attr in ('aria-label', 'title'):
            try:
                a11y += ' ' + (link.get_attribute(attr) or '')
            except Exception:
                pass
        a11y = a11y.lower()
        if any(word in a11y for word in COMPLETED_TEXT):
            return True

        # Completed cards get a ✓ inserted as a pseudo-element or icon span.
        # Detect it by looking for a common sibling/ancestor class.
        parent = link
        for _ in range(4):
            try:
                outer = parent.get_attribute('outerHTML') or ''
                if ('✓' in outer or 'completed' in outer.lower() or
                        'claimed' in outer.lower()):
                    return True
                parent = parent.find_element(By.XPATH, '..')
            except (NoSuchElementException, StaleElementReferenceException):
                break
            except Exception:
                break
    except Exception:
        pass
    return False




def _try_click_card(driver, card, idx: int, result: DailySetResult) -> bool:
    """Click a single card link — the click is Bing's point trigger."""
    try:
        if not card.is_displayed() or not card.is_enabled():
            result.cards_skipped += 1
            return False
        # Scroll the element into view — out-of-viewport elements may not
        # receive a click without this.
        try:
            driver.execute_script('arguments[0].scrollIntoView({block: "center"});', card)
            time.sleep(0.5)
        except Exception:
            pass
        card.click()
        result.cards_clicked += 1
        result.details.append(_card_label(card)[:60] + ' → clicked')
        # Wait briefly — clicking may open a new tab (offer pages) or do an
        # SPA redirect; we do NOT need to wait for navigation to settle.
        time.sleep(2.0 + random.uniform(0, 2.0))
        return True
    except (StaleElementReferenceException, TimeoutException) as exc:
        logger.debug('card %d click went stale: %s', idx, exc)
        result.cards_skipped += 1
        return False
    except Exception as exc:
        logger.debug('card %d click error: %s', idx, exc)
        result.cards_skipped += 1
        return False


def _read_final_balance(driver, result: DailySetResult) -> None:
    """Read the rewards balance after all cards — store in result."""
    medallion = rewards.read_medallion(driver)
    if medallion is not None and medallion.points is not None:
        result.points_after = medallion.points
    else:
        try:
            dash = rewards.read_status(driver)
            result.points_after = dash.points
        except Exception:
            pass
