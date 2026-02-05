"""Data Collection Agent - Fetches market and social media data."""

from datetime import datetime
from typing import Dict, List
from uuid import UUID

from crewai import Agent, Task

from ..config import get_settings
from ..database import get_db_manager
from ..database.models import Contract, SocialPost, HistoricalOdds
from ..services import PolymarketAPI, TwitterScraper, RedditScraper
from ..utils.logger import get_logger

logger = get_logger(__name__)


class DataCollectionAgent:
    """
    Agent responsible for collecting data from Polymarket and social media.

    Responsibilities:
    - Fetch active Polymarket contracts
    - Collect Twitter/X posts related to contracts
    - Collect Reddit posts related to contracts
    - Store all data in PostgreSQL database
    - Track historical odds changes
    """

    def __init__(self):
        """Initialize Data Collection Agent."""
        self.settings = get_settings()
        self.db_manager = get_db_manager()

        # Initialize service integrations
        self.polymarket = PolymarketAPI()
        self.twitter = TwitterScraper()
        self.reddit = RedditScraper()

        logger.info("Data Collection Agent initialized")

    def create_crewai_agent(self) -> Agent:
        """
        Create CrewAI agent definition.

        Returns:
            CrewAI Agent instance
        """
        return Agent(
            role='Data Collection Specialist',
            goal='Gather comprehensive market and social media data for analysis',
            backstory="""You are an expert data collector specializing in prediction markets
            and social media intelligence. You know how to efficiently gather relevant data
            from multiple sources while respecting rate limits and API terms of service.""",
            verbose=True,
            allow_delegation=False
        )

    def collect_market_data(self) -> List[Dict]:
        """
        Collect active Polymarket contracts.

        Returns:
            List of contract dictionaries with metadata
        """
        logger.info("Starting market data collection...")

        try:
            # Fetch active markets from Polymarket
            markets = self.polymarket.get_active_markets(
                limit=self.settings.max_contracts_per_cycle
            )

            contracts_data = []

            with self.db_manager.get_session() as session:
                for market in markets:
                    # Parse market to standardized format
                    contract_data = self.polymarket.parse_market_to_contract(market)
                    if not contract_data.get('contract_id'):
                        continue

                    # Check if contract exists in database
                    existing = session.query(Contract).filter(
                        Contract.contract_id == contract_data['contract_id']
                    ).first()

                    if existing:
                        # Update existing contract
                        for key, value in contract_data.items():
                            if key not in ['raw_data', 'created_at']:
                                setattr(existing, key, value)

                        # Record historical odds if they changed
                        if (contract_data.get('current_yes_odds') and
                            contract_data['current_yes_odds'] != existing.current_yes_odds):

                            historical = HistoricalOdds(
                                contract_id=existing.id,
                                yes_odds=contract_data['current_yes_odds'],
                                no_odds=contract_data['current_no_odds'],
                                volume=contract_data.get('volume_24h')
                            )
                            session.add(historical)

                        contract_obj = existing
                    else:
                        # Create new contract (exclude raw_data which is not a model field)
                        db_data = {k: v for k, v in contract_data.items() if k != 'raw_data'}
                        contract_obj = Contract(**db_data)
                        session.add(contract_obj)
                        session.flush()  # Get ID for historical odds

                        # Add initial historical odds
                        if contract_data.get('current_yes_odds'):
                            historical = HistoricalOdds(
                                contract_id=contract_obj.id,
                                yes_odds=contract_data['current_yes_odds'],
                                no_odds=contract_data['current_no_odds'],
                                volume=contract_data.get('volume_24h')
                            )
                            session.add(historical)

                    contracts_data.append({
                        'id': str(contract_obj.id),
                        'contract_id': contract_obj.contract_id,
                        'question': contract_obj.question,
                        'category': contract_obj.category
                    })

                session.commit()

            logger.info(f"Collected {len(contracts_data)} market contracts")
            return contracts_data

        except Exception as e:
            logger.error(f"Error collecting market data: {e}")
            return []

    def collect_social_media_data(self, contracts: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Collect social media posts related to contracts.

        Args:
            contracts: List of contract dictionaries

        Returns:
            Dictionary mapping contract IDs to social posts
        """
        logger.info(f"Starting social media data collection for {len(contracts)} contracts...")

        results = {}
        hours_back = self.settings.data_collection_lookback_hours

        for contract in contracts[:10]:  # Limit to avoid rate limits
            contract_id = contract['id']
            question = contract['question']

            logger.info(f"Collecting social data for: {question[:50]}...")

            posts = []

            # Extract keywords from question
            keywords = self._extract_keywords(question)

            # Collect Twitter data
            if self.twitter.enabled:
                try:
                    for keyword in keywords[:3]:  # Limit keywords
                        twitter_posts = self.twitter.search_tweets(
                            query=keyword,
                            max_results=20,
                            hours_back=hours_back
                        )
                        posts.extend(twitter_posts)
                except Exception as e:
                    logger.error(f"Error collecting Twitter data: {e}")

            # Collect Reddit data
            if self.reddit.enabled:
                try:
                    # Get relevant subreddits based on category
                    subreddits = self.reddit.get_relevant_subreddits(
                        contract.get('category', '')
                    )

                    for keyword in keywords[:3]:
                        reddit_posts = self.reddit.search_multiple_subreddits(
                            subreddits=subreddits[:3],  # Limit subreddits
                            query=keyword,
                            max_per_subreddit=10,
                            hours_back=hours_back
                        )
                        posts.extend(reddit_posts)
                except Exception as e:
                    logger.error(f"Error collecting Reddit data: {e}")

            # Store posts in database
            if posts:
                stored_posts = self._store_social_posts(posts, contract_id)
                results[contract_id] = stored_posts

            logger.info(f"Collected {len(posts)} social posts for contract {contract_id}")

        logger.info(f"Social media collection complete: {sum(len(p) for p in results.values())} total posts")
        return results

    def _store_social_posts(self, posts: List[Dict], contract_id: str) -> List[Dict]:
        """
        Store social media posts in database.

        Args:
            posts: List of post dictionaries
            contract_id: Associated contract UUID

        Returns:
            List of stored post dictionaries
        """
        stored_posts = []

        try:
            with self.db_manager.get_session() as session:
                for post_data in posts:
                    # Check if post already exists
                    existing = session.query(SocialPost).filter(
                        SocialPost.post_id == post_data['post_id']
                    ).first()

                    if existing:
                        # Update related contracts if needed
                        if contract_id not in [str(c) for c in (existing.related_contracts or [])]:
                            contracts_list = list(existing.related_contracts or [])
                            contracts_list.append(UUID(contract_id))
                            existing.related_contracts = contracts_list
                        continue

                    # Create new post
                    post = SocialPost(
                        post_id=post_data['post_id'],
                        platform=post_data['platform'],
                        author=post_data.get('author'),
                        content=post_data['content'],
                        url=post_data.get('url'),
                        engagement_score=post_data.get('engagement_score', 0),
                        posted_at=post_data['posted_at'],
                        related_contracts=[UUID(contract_id)]
                    )
                    session.add(post)
                    stored_posts.append(post_data)

                session.commit()

        except Exception as e:
            logger.error(f"Error storing social posts: {e}")

        return stored_posts

    @staticmethod
    def _extract_keywords(question: str) -> List[str]:
        """
        Extract search keywords from question.

        Args:
            question: Market question

        Returns:
            List of keywords
        """
        # Simple extraction - remove common words
        common_words = {
            'will', 'the', 'be', 'in', 'to', 'of', 'and', 'or', 'a', 'an',
            'by', 'on', 'at', 'for', 'with', 'from', 'have', 'has'
        }

        words = question.lower().replace('?', '').replace(',', '').split()
        keywords = [w for w in words if len(w) > 3 and w not in common_words]

        return keywords[:5]

    def create_collection_task(self) -> Task:
        """
        Create CrewAI task for data collection.

        Returns:
            CrewAI Task instance
        """
        return Task(
            description="""Collect comprehensive data from Polymarket and social media:
            1. Fetch active Polymarket contracts (up to {max_contracts})
            2. For each contract, extract relevant keywords
            3. Search Twitter/X for related posts from last {hours} hours
            4. Search Reddit for related posts from last {hours} hours
            5. Store all data in PostgreSQL database
            6. Track historical odds changes
            """.format(
                max_contracts=self.settings.max_contracts_per_cycle,
                hours=self.settings.data_collection_lookback_hours
            ),
            agent=self.create_crewai_agent(),
            expected_output="Dictionary containing collected contracts and social media posts"
        )

    def run(self) -> Dict:
        """
        Execute data collection workflow.

        Returns:
            Dictionary with collection results
        """
        logger.info("=== Starting Data Collection Agent ===")

        # Collect market data
        contracts = self.collect_market_data()

        # Collect social media data
        social_data = self.collect_social_media_data(contracts)

        results = {
            'contracts': contracts,
            'social_posts': social_data,
            'timestamp': datetime.utcnow().isoformat()
        }

        logger.info(f"Data collection complete: {len(contracts)} contracts, "
                   f"{sum(len(p) for p in social_data.values())} social posts")

        return results
