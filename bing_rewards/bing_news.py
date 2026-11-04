# SPDX-FileCopyrightText: 2026 jack-mil
# SPDX-License-Identifier: MIT

"""Read Bing news articles for Microsoft Rewards points.

Bing Rewards gives ~30 points/day for reading news articles on Bing/MSN.
This module navigates to Bing news, clicks through articles, and waits for
them to register as "read" server-side.
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

BING_NEWS_URL = 'https://www.bing.com/news'
MSN_NEWS_URL = 'https://www.msn.com/en-us/news'


class BingNewsResult:
    """Outcome of one Bing news reading run."""

    def __init__(self) -> None:
        self.articles_found: int = 0
        self.articles_read: int = 0
        self.articles_skipped: int = 0

    def summary(self) -> str:
        return (
            f'Bing News: read {self.articles_read}/{self.articles_found} '
            f'articles ({self.articles_skipped} skipped)'
        )


def run_bing_news(driver) -> BingNewsResult:
    """Read Bing news articles to earn daily reading points.

    Strategy: navigate to Bing news, find article links, click each one,
    wait briefly for the page to load (Bing registers the read server-side),
    then navigate back to the news feed for the next article.
    """
    result = BingNewsResult()

    try:
        driver.get(BING_NEWS_URL)
        WebDriverWait(driver, 15, poll_frequency=0.5).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, 'a[href*="/news"]') or
                      d.find_elements(By.TAG_NAME, 'article')
        )
        time.sleep(2.0 + random.uniform(0, 2.0))
    except (TimeoutException, Exception) as exc:
        logger.warning('could not reach Bing news (%s)', exc)
        return result

    # Find article links — Bing news uses various selectors
    article_selectors = [
        'a[href*="bing.com/news"]',
        'a[href*="msn.com"]',
        'a[href*="/news/search"]',
        '.news-card a',
        'article a',
        '[data-bi-name="title"] a',
    ]

    articles = []
    seen_urls = set()
    for sel in article_selectors:
        try:
            links = driver.find_elements(By.CSS_SELECTOR, sel)
            for link in links:
                try:
                    href = (link.get_attribute('href') or '').strip()
                    if not href or href in seen_urls:
                        continue
                    # Skip non-article links (navigation, search, etc.)
                    if any(skip in href.lower() for skip in ['/search?', '/images', '/videos', 'javascript:']):
                        continue
                    seen_urls.add(href)
                    articles.append(link)
                except (StaleElementReferenceException, NoSuchElementException):
                    continue
        except Exception:
            continue

    # Deduplicate by href
    unique_articles = []
    seen = set()
    for art in articles:
        try:
            href = (art.get_attribute('href') or '').strip()
            if href not in seen:
                seen.add(href)
                unique_articles.append(art)
        except Exception:
            continue

    articles = unique_articles[:15]  # Read up to 15 articles per day
    result.articles_found = len(articles)

    if not articles:
        logger.info('no news articles found on Bing news page')
        return result

    logger.info('found %d news articles to read', len(articles))

    for idx, article in enumerate(articles):
        try:
            if not article.is_displayed() or not article.is_enabled():
                result.articles_skipped += 1
                continue

            title = (article.text or '').strip()[:60] or '(untitled)'
            logger.info('reading article %d/%d: %s', idx + 1, len(articles), title)

            # Scroll into view
            try:
                driver.execute_script('arguments[0].scrollIntoView({block: "center"});', article)
                time.sleep(0.5)
            except Exception:
                pass

            article.click()
            # Wait for the article page to load — Bing registers the read
            time.sleep(3.0 + random.uniform(1.0, 3.0))

            result.articles_read += 1

            # Navigate back to news feed
            driver.get(BING_NEWS_URL)
            WebDriverWait(driver, 10, poll_frequency=0.5).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, 'a[href*="/news"]') or
                          d.find_elements(By.TAG_NAME, 'article')
            )
            time.sleep(1.5 + random.uniform(0, 1.5))

            # Re-find articles after page reload (elements go stale)
            new_articles = []
            seen_new = set()
            for sel in article_selectors:
                try:
                    links = driver.find_elements(By.CSS_SELECTOR, sel)
                    for link in links:
                        try:
                            href = (link.get_attribute('href') or '').strip()
                            if href and href not in seen_new and href not in seen:
                                seen_new.add(href)
                                new_articles.append(link)
                        except Exception:
                            continue
                except Exception:
                    continue
            # Replace remaining articles with newly found ones
            if new_articles and idx + 1 < len(articles):
                articles[idx + 1:] = new_articles[:len(articles) - idx - 1]

        except (StaleElementReferenceException, TimeoutException) as exc:
            logger.debug('article %d went stale: %s', idx, exc)
            result.articles_skipped += 1
            # Try to get back to news feed
            try:
                driver.get(BING_NEWS_URL)
                time.sleep(2.0)
            except Exception:
                pass
        except Exception as exc:
            logger.debug('article %d error: %s', idx, exc)
            result.articles_skipped += 1

    logger.info(result.summary())
    return result
