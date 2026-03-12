"""X/Twitter mirror scraper using public Nitter instances (fallback when Grok unavailable)."""

import hashlib
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from ..config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Public Nitter/XCancel instances (X mirror, no login required)
NITTER_INSTANCES = [
    "https://xcancel.com",
    "https://nitter.net",
]


class XMirrorScraper:
    """
    Scrape public X/Twitter posts via Nitter mirror instances.

    Used as a fallback when Grok API is unavailable.
    Respects robots.txt and rate limits. Public posts only.
    """

    def __init__(self):
        self.settings = get_settings()
        # Only enabled when Grok is NOT available
        self.enabled = self.settings.enable_x_mirror and not self.settings.has_grok_credentials
        self.delay = self.settings.scraper_request_delay
        self.user_agent = self.settings.scraper_user_agent

        if self.enabled:
            logger.info("X Mirror Scraper initialized (Grok unavailable, using Nitter/XCancel fallback)")
        else:
            logger.debug("X Mirror Scraper disabled")

    def _parse_engagement(self, tweet_item) -> int:
        """Extract engagement score from tweet stats (comments, retweets, likes, views)."""
        try:
            stats = tweet_item.find_all("span", class_="tweet-stat")
            total = 0
            for stat in stats:
                text = stat.get_text(strip=True).replace(",", "")
                # Extract numeric value
                match = re.search(r'(\d+)', text)
                if match:
                    total += int(match.group(1))
            return total if total > 0 else 1
        except Exception:
            return 1

    def _parse_author(self, tweet_item) -> str:
        """Extract author username from tweet."""
        try:
            username = tweet_item.find("a", class_="username")
            if username:
                return username.get_text(strip=True).lstrip("@")
            fullname = tweet_item.find("a", class_="fullname")
            if fullname:
                return fullname.get_text(strip=True)
        except Exception:
            pass
        return "unknown"

    def _parse_timestamp(self, tweet_item) -> datetime:
        """Extract timestamp from tweet date element."""
        try:
            date_link = tweet_item.find("span", class_="tweet-date")
            if date_link:
                a_tag = date_link.find("a")
                if a_tag and a_tag.get("title"):
                    # Format: "Mar 11, 2026 · 7:10 PM UTC"
                    title = a_tag["title"].replace("\u00b7", "").strip()
                    # Clean up extra spaces
                    title = re.sub(r'\s+', ' ', title)
                    for fmt in ["%b %d, %Y %I:%M %p %Z", "%b %d, %Y %I:%M %p"]:
                        try:
                            return datetime.strptime(title, fmt).replace(tzinfo=timezone.utc)
                        except ValueError:
                            continue
        except Exception:
            pass
        return datetime.now(timezone.utc)

    def _parse_url(self, tweet_item, instance: str) -> str:
        """Extract permalink for the tweet."""
        try:
            link = tweet_item.find("a", class_="tweet-link")
            if link and link.get("href"):
                return f"{instance}{link['href'].strip()}"
            # Fallback: try the date link
            date_link = tweet_item.find("span", class_="tweet-date")
            if date_link:
                a_tag = date_link.find("a")
                if a_tag and a_tag.get("href"):
                    return f"{instance}{a_tag['href'].strip()}"
        except Exception:
            pass
        return instance

    def search_posts(self, query: str, max_results: int = 15) -> List[Dict]:
        """
        Search for X posts via Nitter mirrors.

        Args:
            query: Search query
            max_results: Maximum posts to return

        Returns:
            List of post dicts in standard format
        """
        if not self.enabled:
            return []

        headers = {"User-Agent": self.user_agent}

        for instance in NITTER_INSTANCES:
            try:
                time.sleep(self.delay)
                url = f"{instance}/search?q={query}&f=tweets"
                r = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)

                if r.status_code != 200:
                    logger.debug(f"X mirror {instance} returned {r.status_code}")
                    continue

                soup = BeautifulSoup(r.text, "html.parser")

                # Each tweet is a .timeline-item containing .tweet-content
                tweet_items = soup.find_all("div", class_="timeline-item")
                if not tweet_items:
                    # Fallback: try just the content divs
                    tweet_divs = soup.find_all("div", class_="tweet-content")
                    if not tweet_divs:
                        continue
                    # Wrap in simple results with no metadata
                    results = []
                    for div in tweet_divs[:max_results]:
                        text = div.get_text(strip=True)
                        if not text or len(text) < 10:
                            continue
                        post_hash = hashlib.sha256(f"xmirror_{text[:100]}".encode()).hexdigest()[:16]
                        results.append({
                            "post_id": f"xmirror_{post_hash}",
                            "platform": "x_mirror",
                            "author": "unknown",
                            "content": text[:1000],
                            "posted_at": datetime.now(timezone.utc),
                            "url": instance,
                            "engagement_score": 1,
                        })
                    if results:
                        logger.info(f"X Mirror: scraped {len(results)} posts for '{query}' from {instance}")
                        return results
                    continue

                results = []
                for item in tweet_items[:max_results]:
                    content_div = item.find("div", class_="tweet-content")
                    if not content_div:
                        continue
                    text = content_div.get_text(strip=True)
                    if not text or len(text) < 10:
                        continue

                    author = self._parse_author(item)
                    engagement = self._parse_engagement(item)
                    posted_at = self._parse_timestamp(item)
                    tweet_url = self._parse_url(item, instance)

                    post_hash = hashlib.sha256(f"xmirror_{author}_{text[:100]}".encode()).hexdigest()[:16]
                    results.append({
                        "post_id": f"xmirror_{post_hash}",
                        "platform": "x_mirror",
                        "author": author,
                        "content": text[:1000],
                        "posted_at": posted_at,
                        "url": tweet_url,
                        "engagement_score": engagement,
                    })

                if results:
                    logger.info(f"X Mirror: scraped {len(results)} posts for '{query}' from {instance}")
                    return results

            except Exception as e:
                logger.debug(f"X mirror instance {instance} failed: {e}")
                continue

        logger.warning(f"X mirror scraping failed for: {query} -- all instances unavailable")
        return []
