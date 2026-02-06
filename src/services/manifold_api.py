"""Manifold Markets prediction market API client (free, no authentication required)."""

import time
from typing import Dict, List, Optional

import requests
from ratelimit import limits, sleep_and_retry
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

BASE_URL = "https://api.manifold.markets"


class ManifoldAPI:
    """
    Manifold Markets API client for fetching prediction market data.

    No authentication required for read operations.
    Play-money market but probabilities are still useful as prediction signals.
    Rate limited to 500 requests per minute.
    """

    def __init__(self):
        """Initialize Manifold API client."""
        self.settings = get_settings()
        self.enabled = self.settings.enable_manifold
        self.session = self._create_session()

        if self.enabled:
            logger.info("Manifold Markets API client initialized")
        else:
            logger.info("Manifold Markets API client disabled")

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
    @limits(calls=30, period=60)
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional:
        """Make rate-limited API request."""
        try:
            url = f"{BASE_URL}{endpoint}"
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                logger.warning("Manifold rate limit hit, backing off...")
                time.sleep(10)
            else:
                logger.error(f"Manifold API HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"Manifold API request error: {e}")
            return None

    def search_markets(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search Manifold markets by text query.

        Args:
            query: Search query string
            limit: Maximum results to return

        Returns:
            List of standardized market dicts
        """
        if not self.enabled:
            return []

        try:
            params = {
                "term": query,
                "filter": "open",
                "contractType": "BINARY",
                "sort": "score",
                "limit": min(limit, 100),
            }

            data = self._make_request("/v0/search-markets", params)
            if not data or not isinstance(data, list):
                return []

            results = []
            for market in data:
                parsed = self._parse_market(market)
                if parsed:
                    results.append(parsed)

            logger.info(f"Manifold: found {len(results)} markets matching '{query}'")
            return results

        except Exception as e:
            logger.error(f"Error searching Manifold markets: {e}")
            return []

    def get_market(self, market_id: str) -> Optional[Dict]:
        """
        Get a specific Manifold market by ID.

        Args:
            market_id: Manifold market ID

        Returns:
            Standardized market dict or None
        """
        if not self.enabled:
            return None

        data = self._make_request(f"/v0/market/{market_id}")
        if not data:
            return None

        return self._parse_market(data)

    def _parse_market(self, market: Dict) -> Optional[Dict]:
        """
        Parse a Manifold market into standardized format.

        Args:
            market: Raw market object from API

        Returns:
            Standardized market dict or None
        """
        try:
            question = market.get("question", "")
            probability = market.get("probability")

            if probability is None:
                return None

            market_id = market.get("id", "")
            url = market.get("url") or f"https://manifold.markets/market/{market_id}"

            return {
                "platform": "manifold",
                "market_id": market_id,
                "question": question,
                "probability": float(probability),
                "volume": market.get("volume") or 0,
                "url": url,
                "status": "resolved" if market.get("isResolved") else "open",
            }

        except Exception as e:
            logger.debug(f"Error parsing Manifold market: {e}")
            return None
