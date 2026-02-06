"""Data Collection Agent - Fetches market and social media data."""

from datetime import datetime, timezone
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
        self.rss_news = None

        # Initialize RSS news scraper (always available, no API keys needed)
        try:
            from ..services import RSSNewsScraper
            self.rss_news = RSSNewsScraper()
            logger.info("RSS News scraper initialized (FREE news source)")
        except Exception as e:
            logger.warning(f"Could not initialize RSS news scraper: {e}")

        # Initialize Bluesky scraper (always available, no API keys needed)
        self.bluesky = None
        try:
            from ..services import BlueskyScraper
            self.bluesky = BlueskyScraper()
            logger.info("Bluesky scraper initialized (FREE social media source)")
        except Exception as e:
            logger.warning(f"Could not initialize Bluesky scraper: {e}")

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
            # Fetch more markets than needed since many will be expired
            # and filtered out. Fetch 5x the target to ensure enough remain.
            fetch_limit = self.settings.max_contracts_per_cycle * 5
            markets = self.polymarket.get_active_markets(
                limit=fetch_limit
            )

            contracts_data = []

            with self.db_manager.get_session() as session:
                for market in markets:
                    # Parse market to standardized format
                    contract_data = self.polymarket.parse_market_to_contract(market)
                    if not contract_data.get('contract_id'):
                        continue

                    # Skip expired contracts
                    if contract_data.get('end_date'):
                        if contract_data['end_date'] < datetime.now(timezone.utc):
                            logger.debug(f"Skipping expired contract: {contract_data.get('question', 'Unknown')[:50]}")
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

            # Collect Bluesky data (FREE, always available)
            if self.bluesky and self.bluesky.enabled:
                try:
                    for keyword in keywords[:3]:
                        bsky_posts = self.bluesky.search_posts(
                            query=keyword,
                            max_results=25,
                            hours_back=hours_back
                        )
                        posts.extend(bsky_posts)
                    logger.info(f"Collected {len([p for p in posts if p.get('platform') == 'bluesky'])} Bluesky posts")
                except Exception as e:
                    logger.error(f"Error collecting Bluesky data: {e}")

            # Collect RSS news data (FREE, always available)
            if self.rss_news:
                try:
                    news_articles = self.rss_news.search_news(
                        keywords=keywords[:5],  # Use more keywords for news
                        hours_back=hours_back
                    )

                    # Convert news articles to social post format
                    for article in news_articles[:20]:  # Limit to 20 articles
                        posts.append({
                            'post_id': f"rss_{hash(article['url'])}",  # Generate unique ID
                            'platform': 'news_rss',
                            'author': article['author'],
                            'content': f"{article['title']}: {article['content']}",
                            'posted_at': article['published_at'],  # Fixed: changed from created_at to posted_at
                            'url': article['url'],
                            'engagement_score': 50,  # Default score for news
                            'source_name': article['source']
                        })

                    logger.info(f"Collected {len(news_articles)} news articles from RSS feeds")
                except Exception as e:
                    logger.error(f"Error collecting RSS news data: {e}")

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

        Deduplicates posts by post_id before inserting and handles
        conflicts gracefully so one bad post doesn't fail the batch.

        Args:
            posts: List of post dictionaries
            contract_id: Associated contract UUID

        Returns:
            List of stored post dictionaries
        """
        stored_posts = []

        # Deduplicate incoming posts by post_id
        seen = set()
        unique_posts = []
        for p in posts:
            pid = p.get('post_id')
            if pid and pid not in seen:
                seen.add(pid)
                unique_posts.append(p)

        try:
            with self.db_manager.get_session() as session:
                for post_data in unique_posts:
                    try:
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
                        session.flush()  # Flush each post so duplicates don't poison the batch
                        stored_posts.append(post_data)

                    except Exception as e:
                        session.rollback()
                        logger.debug(f"Skipped post {post_data.get('post_id', '?')}: {e}")

                session.commit()

        except Exception as e:
            logger.error(f"Error storing social posts: {e}")

        return stored_posts

    @staticmethod
    def _extract_keywords(question: str) -> List[str]:
        """
        Extract meaningful search keywords from a Polymarket question.

        Filters out stop words, numbers, price tokens, and generic terms
        to produce keywords that will return relevant social media results.

        Args:
            question: Market question

        Returns:
            List of keywords (most specific first)
        """
        import re

        stop_words = {
            # Determiners / articles
            'the', 'a', 'an', 'this', 'that', 'these', 'those',
            # Prepositions
            'in', 'on', 'at', 'to', 'for', 'of', 'by', 'with', 'from',
            'into', 'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'under', 'over', 'about', 'against', 'within',
            # Conjunctions
            'and', 'or', 'but', 'nor', 'yet', 'so',
            # Pronouns
            'he', 'she', 'it', 'they', 'them', 'his', 'her', 'its', 'their',
            'who', 'whom', 'which', 'what', 'whose',
            # Common verbs
            'will', 'would', 'could', 'should', 'shall', 'may', 'might',
            'can', 'does', 'did', 'has', 'have', 'had', 'been', 'being',
            'was', 'were', 'are', 'is', 'be', 'do', 'get', 'got',
            'become', 'reach', 'exceed', 'fall', 'rise', 'drop', 'hit',
            'remain', 'stay', 'happen', 'occur', 'take', 'make', 'go',
            'win', 'lose', 'pass', 'fail', 'sign', 'announce', 'report',
            'increase', 'decrease', 'collect', 'receive', 'give', 'keep',
            'hold', 'release', 'close', 'open', 'set', 'run', 'lead',
            'move', 'change', 'turn', 'show', 'come', 'leave', 'call',
            'pay', 'play', 'put', 'bring', 'use', 'try', 'ask', 'tell',
            'say', 'said', 'know', 'think', 'see', 'want', 'need', 'look',
            'find', 'give', 'work', 'seem', 'feel', 'provide', 'include',
            'consider', 'appear', 'allow', 'meet', 'add', 'expect',
            'continue', 'create', 'offer', 'serve', 'cause', 'require',
            'follow', 'agree', 'support', 'produce', 'lose', 'return',
            # Generic nouns (too broad for useful search)
            'yes', 'no', 'more', 'less', 'than',
            'least', 'most', 'end', 'start', 'begin', 'next', 'last', 'first',
            'many', 'much', 'some', 'any', 'each', 'every', 'all',
            'other', 'another', 'such', 'only', 'also', 'just',
            'how', 'when', 'where', 'why', 'whether',
            'per', 'cost', 'price', 'total', 'number', 'amount',
            'people', 'person', 'year', 'years', 'month', 'months',
            'day', 'days', 'week', 'weeks', 'time', 'date',
            'level', 'rate', 'share', 'point', 'part', 'place',
            'case', 'group', 'company', 'system', 'program', 'question',
            'government', 'world', 'area', 'state', 'states',
            'market', 'markets', 'billion', 'million', 'trillion',
            'average', 'high', 'low', 'new', 'old', 'long', 'short',
            'revenue', 'value', 'growth', 'result', 'report', 'data',
            'percent', 'currently', 'based', 'likely', 'according',
            'announced', 'expected', 'still', 'even', 'well', 'back',
            'official', 'officially', 'current', 'annual', 'daily',
            'approximately', 'roughly', 'estimated', 'around',
        }

        # Clean the question
        text = question.replace('?', '').replace(',', '').replace("'s", '')

        # Remove dollar amounts, percentages, and number ranges
        text = re.sub(r'\$[\d,.]+\+?', '', text)
        text = re.sub(r'[\d,.]+%', '', text)
        text = re.sub(r'[\d,.]+-[\d,.]+', '', text)
        text = re.sub(r'\b\d{1,3}(,\d{3})+\b', '', text)  # e.g. 1,750,000

        words = text.split()

        # Keep capitalized words (proper nouns) with priority
        proper_nouns = []
        regular_words = []
        for w in words:
            clean = re.sub(r'[^a-zA-Z]', '', w)
            if len(clean) < 3:
                continue
            if clean.lower() in stop_words:
                continue
            if w[0].isupper():
                proper_nouns.append(clean)
            else:
                regular_words.append(clean.lower())

        # Proper nouns first (Trump, Bitcoin, etc.), then other meaningful words
        keywords = proper_nouns + regular_words

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                unique.append(kw)

        # If no proper nouns were found and only 1 generic word remains,
        # the keywords aren't specific enough for useful search results
        if not proper_nouns and len(unique) <= 1:
            return []

        return unique[:5]

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
