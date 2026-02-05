"""Polymarket API integration with ethical data fetching."""

import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from ratelimit import limits, sleep_and_retry

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PolymarketAPI:
    """
    Ethical Polymarket API client with rate limiting and retry logic.

    Respects platform terms of service and implements best practices:
    - Rate limiting per API guidelines
    - Retry logic with exponential backoff
    - User agent identification
    - Proper error handling
    """

    def __init__(self):
        """Initialize Polymarket API client."""
        self.settings = get_settings()
        self.base_url = self.settings.polymarket_api_url
        self.gamma_url = self.settings.polymarket_gamma_api_url
        self.strapi_url = self.settings.polymarket_strapi_url

        # Configure session with retry logic
        self.session = self._create_session()

        # Rate limiting configuration (10 requests per minute by default)
        self.rate_limit_calls = self.settings.polymarket_rate_limit
        self.rate_limit_period = 60  # seconds

        logger.info("Polymarket API client initialized")

    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic."""
        session = requests.Session()

        # Retry strategy
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1  # 1, 2, 4 seconds
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set user agent
        session.headers.update({
            'User-Agent': 'PolymarketGapDetector/1.0 (Educational Research)',
            'Accept': 'application/json'
        })

        return session

    @sleep_and_retry
    @limits(calls=10, period=60)  # Rate limit: 10 calls per minute
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """
        Make rate-limited API request.

        Args:
            url: API endpoint URL
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            requests.RequestException: If request fails
        """
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.warning("Rate limit hit, backing off...")
                time.sleep(60)
                return self._make_request(url, params)
            logger.error(f"HTTP error: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            raise

    def get_active_markets(self, limit: int = 100) -> List[Dict]:
        """
        Fetch active prediction markets.

        Args:
            limit: Maximum number of markets to fetch

        Returns:
            List of market dictionaries
        """
        try:
            # Use Gamma API to get markets
            url = f"{self.gamma_url}/markets"
            params = {
                'closed': 'false',
                'limit': min(limit, 100),  # API max
                'offset': 0
            }

            logger.info(f"Fetching active markets (limit={limit})")
            response = self._make_request(url, params)

            markets = response if isinstance(response, list) else response.get('data', [])
            logger.info(f"Fetched {len(markets)} active markets")

            return markets

        except Exception as e:
            logger.error(f"Error fetching active markets: {e}")
            return []

    def get_market_details(self, condition_id: str) -> Optional[Dict]:
        """
        Get detailed information about a specific market.

        Args:
            condition_id: Market condition ID

        Returns:
            Market details dictionary or None if not found
        """
        try:
            url = f"{self.gamma_url}/markets/{condition_id}"
            logger.debug(f"Fetching market details for {condition_id}")

            response = self._make_request(url)
            return response

        except Exception as e:
            logger.error(f"Error fetching market details for {condition_id}: {e}")
            return None

    def get_market_prices(self, condition_id: str) -> Optional[Dict]:
        """
        Get current prices for a market.

        Args:
            condition_id: Market condition ID

        Returns:
            Price data dictionary or None if not found
        """
        try:
            url = f"{self.base_url}/prices"
            params = {'market': condition_id}

            logger.debug(f"Fetching prices for market {condition_id}")
            response = self._make_request(url, params)

            return response

        except Exception as e:
            logger.error(f"Error fetching prices for {condition_id}: {e}")
            return None

    def get_market_orderbook(self, token_id: str) -> Optional[Dict]:
        """
        Get order book for a specific token.

        Args:
            token_id: Token ID

        Returns:
            Order book data or None if not found
        """
        try:
            url = f"{self.base_url}/book"
            params = {'token_id': token_id}

            logger.debug(f"Fetching order book for token {token_id}")
            response = self._make_request(url, params)

            return response

        except Exception as e:
            logger.error(f"Error fetching order book for {token_id}: {e}")
            return None

    def parse_market_to_contract(self, market: Dict) -> Dict:
        """
        Parse Polymarket API response into standardized contract format.

        Args:
            market: Raw market data from API

        Returns:
            Standardized contract dictionary
        """
        try:
            # Validate input is a dictionary
            if not isinstance(market, dict):
                logger.error(f"Expected dict, got {type(market)}: {str(market)[:100]}")
                return {}

            # Extract key fields (Polymarket API structure may vary)
            contract_id = market.get('condition_id') or market.get('id')
            question = market.get('question') or market.get('title', '')
            description = market.get('description', '')

            # Parse end date
            end_date_str = market.get('end_date_iso') or market.get('endDate')
            end_date = None
            if end_date_str:
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                except:
                    pass

            # Get current odds from outcomes
            outcomes = market.get('outcomes', [])
            yes_odds = None
            no_odds = None

            if len(outcomes) >= 2:
                # Typically outcomes[0] is YES, outcomes[1] is NO
                try:
                    # Handle both dict and string outcomes
                    outcome_0 = outcomes[0]
                    outcome_1 = outcomes[1]

                    # If outcomes are dictionaries
                    if isinstance(outcome_0, dict) and isinstance(outcome_1, dict):
                        yes_price = float(outcome_0.get('price', 0))
                        no_price = float(outcome_1.get('price', 0))

                        # Convert price to odds (price is probability)
                        yes_odds = Decimal(str(yes_price))
                        no_odds = Decimal(str(no_price))
                    # If outcomes are strings, try to parse as token IDs
                    elif isinstance(outcome_0, str) or isinstance(outcome_1, str):
                        logger.debug(f"Outcomes are strings (token IDs), fetching prices separately")
                        # We'll skip odds for now, or fetch them via a separate price API call
                        pass
                except (ValueError, TypeError, KeyError, AttributeError) as e:
                    logger.debug(f"Could not parse outcome prices: {e}")

            # Get volume and liquidity
            volume_24h = market.get('volume24hr', 0)
            liquidity = market.get('liquidity', 0)

            return {
                'contract_id': contract_id,
                'question': question,
                'description': description,
                'end_date': end_date,
                'category': market.get('category', 'Unknown'),
                'current_yes_odds': yes_odds,
                'current_no_odds': no_odds,
                'volume_24h': Decimal(str(volume_24h)) if volume_24h else None,
                'liquidity': Decimal(str(liquidity)) if liquidity else None,
                'active': not market.get('closed', False),
                'raw_data': market  # Keep raw data for reference
            }

        except Exception as e:
            logger.error(f"Error parsing market data: {e}")
            logger.debug(f"Market data type: {type(market)}, value: {str(market)[:200]}")
            return {}

    def search_markets(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search markets by keyword.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching markets
        """
        try:
            # Get all active markets and filter client-side
            # (Polymarket may not have a dedicated search endpoint)
            all_markets = self.get_active_markets(limit=100)

            # Simple keyword matching
            query_lower = query.lower()
            matching = [
                m for m in all_markets
                if query_lower in m.get('question', '').lower() or
                   query_lower in m.get('description', '').lower()
            ]

            return matching[:limit]

        except Exception as e:
            logger.error(f"Error searching markets: {e}")
            return []
