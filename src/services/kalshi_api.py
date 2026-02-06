"""Kalshi prediction market API client (free, no authentication required for reads)."""

import time
from typing import Dict, List, Optional

import requests
from ratelimit import limits, sleep_and_retry
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


class KalshiAPI:
    """
    Kalshi API client for fetching prediction market data.

    No authentication required for market data reads.
    Rate limited to stay well under Kalshi's 20 req/sec basic tier.
    """

    def __init__(self):
        """Initialize Kalshi API client."""
        self.settings = get_settings()
        self.enabled = self.settings.enable_kalshi
        self.session = self._create_session()

        if self.enabled:
            logger.info("Kalshi API client initialized")
        else:
            logger.info("Kalshi API client disabled")

    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic."""
        session = requests.Session()

        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            backoff_factor=1
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)

        session.headers.update({
            "Accept": "application/json",
            "User-Agent": "PolymarketGapDetector/1.0 (Educational Research)",
        })

        return session

    @sleep_and_retry
    @limits(calls=10, period=1)
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make rate-limited API request."""
        try:
            url = f"{BASE_URL}{endpoint}"
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                logger.warning("Kalshi rate limit hit, backing off...")
                time.sleep(5)
            else:
                logger.error(f"Kalshi API HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"Kalshi API request error: {e}")
            return None

    def search_markets(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search Kalshi markets by query string.

        Args:
            query: Search query (used to filter by event/market titles)
            limit: Maximum results to return

        Returns:
            List of standardized market dicts
        """
        if not self.enabled:
            return []

        try:
            params = {
                "limit": min(limit, 200),
                "status": "open",
            }

            data = self._make_request("/markets", params)
            if not data or "markets" not in data:
                return []

            raw_markets = data["markets"]

            # Filter client-side by query keywords (Kalshi /markets doesn't have text search)
            query_lower = query.lower()
            query_words = [w for w in query_lower.split() if len(w) > 2]

            matched = []
            for market in raw_markets:
                title = (market.get("title") or "").lower()
                subtitle = (market.get("subtitle") or "").lower()
                event_ticker = (market.get("event_ticker") or "").lower()
                combined = f"{title} {subtitle} {event_ticker}"

                if any(word in combined for word in query_words):
                    parsed = self._parse_market(market)
                    if parsed:
                        matched.append(parsed)

                if len(matched) >= limit:
                    break

            logger.info(f"Kalshi: found {len(matched)} markets matching '{query}'")
            return matched

        except Exception as e:
            logger.error(f"Error searching Kalshi markets: {e}")
            return []

    def search_events(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search Kalshi events and return their child markets.

        Events group related markets (e.g., "2028 Presidential Election"
        contains markets for each candidate).

        Args:
            query: Search query
            limit: Maximum events to fetch

        Returns:
            List of standardized market dicts from matching events
        """
        if not self.enabled:
            return []

        try:
            params = {
                "limit": min(limit, 100),
                "status": "open",
            }

            data = self._make_request("/events", params)
            if not data or "events" not in data:
                return []

            query_lower = query.lower()
            query_words = [w for w in query_lower.split() if len(w) > 2]

            matched_markets = []
            for event in data["events"]:
                title = (event.get("title") or "").lower()
                if any(word in title for word in query_words):
                    # Fetch markets for this event
                    event_ticker = event.get("event_ticker")
                    if event_ticker:
                        event_markets = self._get_event_markets(event_ticker)
                        matched_markets.extend(event_markets)

                if len(matched_markets) >= limit * 3:
                    break

            return matched_markets

        except Exception as e:
            logger.error(f"Error searching Kalshi events: {e}")
            return []

    def _get_event_markets(self, event_ticker: str) -> List[Dict]:
        """Fetch all markets under an event."""
        params = {
            "event_ticker": event_ticker,
            "limit": 50,
        }

        data = self._make_request("/markets", params)
        if not data or "markets" not in data:
            return []

        results = []
        for market in data["markets"]:
            parsed = self._parse_market(market)
            if parsed:
                results.append(parsed)

        return results

    def _parse_market(self, market: Dict) -> Optional[Dict]:
        """
        Parse a Kalshi market into standardized format.

        Args:
            market: Raw market object from API

        Returns:
            Standardized market dict or None
        """
        try:
            ticker = market.get("ticker", "")
            title = market.get("title") or market.get("yes_sub_title") or ""
            subtitle = market.get("subtitle") or ""
            question = f"{title} {subtitle}".strip() if subtitle else title

            # last_price is in cents (0-99), convert to probability (0.0-1.0)
            last_price = market.get("last_price")
            if last_price is None:
                return None

            probability = last_price / 100.0

            # Volume
            volume = market.get("volume_24h_fp") or market.get("volume") or 0

            return {
                "platform": "kalshi",
                "market_id": ticker,
                "question": question,
                "probability": probability,
                "volume": volume,
                "url": f"https://kalshi.com/markets/{ticker}",
                "status": market.get("status", "unknown"),
            }

        except Exception as e:
            logger.debug(f"Error parsing Kalshi market: {e}")
            return None
