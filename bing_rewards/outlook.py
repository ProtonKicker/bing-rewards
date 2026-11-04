# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Read Outlook emails for Microsoft Rewards points.

Microsoft Rewards gives ~10 points/day for reading 3 emails on Outlook mobile/web,
plus weekly streak bonuses. This module navigates to Outlook web and reads emails.
"""

from __future__ import annotations

import logging
import random
import time

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

OUTLOOK_URL = 'https://outlook.live.com/mail/0/'


class OutlookResult:
    """Outcome of one Outlook email reading run."""

    def __init__(self) -> None:
        self.emails_found: int = 0
        self.emails_read: int = 0
        self.emails_skipped: int = 0

    def summary(self) -> str:
        return (
            f'Outlook: read {self.emails_read}/{self.emails_found} '
            f'emails ({self.emails_skipped} skipped)'
        )


def run_outlook_emails(driver) -> OutlookResult:
    """Read Outlook emails to earn daily reading points.

    Strategy: navigate to Outlook web, find email items in the inbox,
    click each one to open/read it, wait briefly, then move to the next.
    """
    result = OutlookResult()

    try:
        driver.get(OUTLOOK_URL)
        WebDriverWait(driver, 20, poll_frequency=0.5).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, '[role="listbox"] [role="option"]') or
                      d.find_elements(By.CSS_SELECTOR, '.ms-List-cell') or
                      d.find_elements(By.CSS_SELECTOR, '[data-convid]')
        )
        time.sleep(3.0 + random.uniform(0, 2.0))
    except (TimeoutException, Exception) as exc:
        logger.warning('could not reach Outlook (%s)', exc)
        return result

    # Find email items in the inbox
    email_selectors = [
        '[role="listbox"] [role="option"]',
        '.ms-List-cell',
        '[data-convid]',
        '[class*="emailItem"]',
        '[class*="mailItem"]',
    ]

    emails = []
    seen = set()
    for sel in email_selectors:
        try:
            items = driver.find_elements(By.CSS_SELECTOR, sel)
            for item in items:
                try:
                    key = (item.get_attribute('data-convid') or
                           item.get_attribute('aria-label') or
                           item.text[:50])
                    if key and key not in seen:
                        seen.add(key)
                        emails.append(item)
                except Exception:
                    continue
            if emails:
                break
        except Exception:
            continue

    emails = emails[:10]  # Read up to 10 emails per day
    result.emails_found = len(emails)

    if not emails:
        logger.info('no emails found in Outlook inbox')
        return result

    logger.info('found %d emails to read', len(emails))

    for idx, email in enumerate(emails):
        try:
            if not email.is_displayed() or not email.is_enabled():
                result.emails_skipped += 1
                continue

            label = (email.get_attribute('aria-label') or email.text or '').strip()[:60]
            logger.info('reading email %d/%d: %s', idx + 1, len(emails), label or '(no subject)')

            # Scroll into view
            try:
                driver.execute_script('arguments[0].scrollIntoView({block: "center"});', email)
                time.sleep(0.5)
            except Exception:
                pass

            email.click()
            # Wait for email to open and register
            time.sleep(3.0 + random.uniform(1.0, 3.0))

            result.emails_read += 1

            # Navigate back to inbox
            driver.get(OUTLOOK_URL)
            WebDriverWait(driver, 15, poll_frequency=0.5).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, '[role="listbox"] [role="option"]') or
                          d.find_elements(By.CSS_SELECTOR, '.ms-List-cell') or
                          d.find_elements(By.CSS_SELECTOR, '[data-convid]')
            )
            time.sleep(1.5 + random.uniform(0, 1.5))

            # Re-find emails after page reload
            new_emails = []
            seen_new = set()
            for sel in email_selectors:
                try:
                    items = driver.find_elements(By.CSS_SELECTOR, sel)
                    for item in items:
                        try:
                            key = (item.get_attribute('data-convid') or
                                   item.get_attribute('aria-label') or
                                   item.text[:50])
                            if key and key not in seen and key not in seen_new:
                                seen_new.add(key)
                                new_emails.append(item)
                        except Exception:
                            continue
                    if new_emails:
                        break
                except Exception:
                    continue
            if new_emails and idx + 1 < len(emails):
                emails[idx + 1:] = new_emails[:len(emails) - idx - 1]

        except (StaleElementReferenceException, TimeoutException) as exc:
            logger.debug('email %d went stale: %s', idx, exc)
            result.emails_skipped += 1
            try:
                driver.get(OUTLOOK_URL)
                time.sleep(2.0)
            except Exception:
                pass
        except Exception as exc:
            logger.debug('email %d error: %s', idx, exc)
            result.emails_skipped += 1

    logger.info(result.summary())
    return result
