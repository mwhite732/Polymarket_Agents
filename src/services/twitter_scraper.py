"""Twitter/X scraping and API integration with ethical data collection."""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from ratelimit import limits, sleep_and_retry

try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False
    print("WARNING: tweepy not installed. Twitter integration will be limited.")

from ..config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class TwitterScraper:
    """
    Ethical Twitter data collector with rate limiting.

    Respects Twitter API terms of service:
    - Uses official API when credentials available
    - Implements proper rate limiting
    - Falls back gracefully when credentials unavailable
    - No unauthorized scraping
    """

    def __init__(self):
        """Initialize Twitter scraper."""
        self.settings = get_settings()
        self.client = None
        self.api = None
        self.enabled = self.settings.enable_twitter and self.settings.has_twitter_credentials

        if self.enabled and TWEEPY_AVAILABLE:
            self._initialize_client()
        else:
            logger.warning("Twitter scraper disabled (no credentials or tweepy not installed)")

    def _initialize_client(self):
        """Initialize Twitter API client."""
        try:
            # Use v2 client with bearer token if available
            if self.settings.twitter_bearer_token:
                self.client = tweepy.Client(
                    bearer_token=self.settings.twitter_bearer_token,
                    wait_on_rate_limit=True
                )
                logger.info("Twitter API v2 client initialized")

            # Also initialize v1.1 API for additional features
            if all([
                self.settings.twitter_api_key,
                self.settings.twitter_api_secret,
                self.settings.twitter_access_token,
                self.settings.twitter_access_secret
            ]):
                auth = tweepy.OAuth1UserHandler(
                    self.settings.twitter_api_key,
                    self.settings.twitter_api_secret,
                    self.settings.twitter_access_token,
                    self.settings.twitter_access_secret
                )
                self.api = tweepy.API(auth, wait_on_rate_limit=True)
                logger.info("Twitter API v1.1 initialized")

        except Exception as e:
            logger.error(f"Error initializing Twitter client: {e}")
            self.enabled = False

    @sleep_and_retry
    @limits(calls=15, period=900)  # 15 calls per 15 minutes
    def search_tweets(
        self,
        query: str,
        max_results: int = 100,
        hours_back: int = 6
    ) -> List[Dict]:
        """
        Search recent tweets matching query.

        Args:
            query: Search query
            max_results: Maximum tweets to return
            hours_back: How many hours back to search

        Returns:
            List of tweet dictionaries
        """
        if not self.enabled or not self.client:
            logger.warning("Twitter search skipped (not enabled)")
            return []

        try:
            # Calculate start time
            start_time = datetime.utcnow() - timedelta(hours=hours_back)

            # Build query with filters
            # Remove retweets and only get tweets with some engagement
            search_query = f"{query} -is:retweet"

            logger.info(f"Searching Twitter for: {search_query}")

            # Search tweets using v2 API
            response = self.client.search_recent_tweets(
                query=search_query,
                start_time=start_time,
                max_results=min(max_results, 100),  # API limit
                tweet_fields=['created_at', 'public_metrics', 'author_id', 'lang'],
                expansions=['author_id'],
                user_fields=['username', 'name']
            )

            if not response.data:
                logger.info(f"No tweets found for query: {query}")
                return []

            # Parse tweets
            tweets = []
            users = {user.id: user for user in response.includes.get('users', [])} if response.includes else {}

            for tweet in response.data:
                author = users.get(tweet.author_id)
                username = author.username if author else 'unknown'

                tweets.append({
                    'post_id': str(tweet.id),
                    'platform': 'twitter',
                    'author': username,
                    'content': tweet.text,
                    'url': f"https://twitter.com/{username}/status/{tweet.id}",
                    'engagement_score': self._calculate_engagement(tweet.public_metrics),
                    'posted_at': tweet.created_at,
                    'raw_data': {
                        'likes': tweet.public_metrics.get('like_count', 0),
                        'retweets': tweet.public_metrics.get('retweet_count', 0),
                        'replies': tweet.public_metrics.get('reply_count', 0),
                        'lang': tweet.lang
                    }
                })

            logger.info(f"Found {len(tweets)} tweets for query: {query}")
            return tweets

        except tweepy.errors.TooManyRequests as e:
            logger.warning("Twitter rate limit hit, backing off...")
            time.sleep(900)  # Wait 15 minutes
            return []
        except Exception as e:
            logger.error(f"Error searching tweets: {e}")
            return []

    def search_tweets_by_keywords(
        self,
        keywords: List[str],
        max_per_keyword: int = 50,
        hours_back: int = 6
    ) -> List[Dict]:
        """
        Search tweets for multiple keywords.

        Args:
            keywords: List of search keywords
            max_per_keyword: Max tweets per keyword
            hours_back: Hours to look back

        Returns:
            Combined list of unique tweets
        """
        all_tweets = []
        seen_ids = set()

        for keyword in keywords:
            tweets = self.search_tweets(
                query=keyword,
                max_results=max_per_keyword,
                hours_back=hours_back
            )

            # Deduplicate
            for tweet in tweets:
                if tweet['post_id'] not in seen_ids:
                    all_tweets.append(tweet)
                    seen_ids.add(tweet['post_id'])

            # Rate limiting between keywords
            time.sleep(2)

        logger.info(f"Collected {len(all_tweets)} unique tweets across {len(keywords)} keywords")
        return all_tweets

    def get_user_tweets(
        self,
        username: str,
        max_results: int = 50,
        hours_back: int = 24
    ) -> List[Dict]:
        """
        Get recent tweets from a specific user.

        Args:
            username: Twitter username (without @)
            max_results: Maximum tweets to return
            hours_back: Hours to look back

        Returns:
            List of tweet dictionaries
        """
        if not self.enabled or not self.client:
            logger.warning("Twitter user lookup skipped (not enabled)")
            return []

        try:
            # Get user ID
            user = self.client.get_user(username=username)
            if not user.data:
                logger.warning(f"User not found: {username}")
                return []

            user_id = user.data.id
            start_time = datetime.utcnow() - timedelta(hours=hours_back)

            # Get user's tweets
            response = self.client.get_users_tweets(
                id=user_id,
                start_time=start_time,
                max_results=min(max_results, 100),
                tweet_fields=['created_at', 'public_metrics'],
                exclude=['retweets', 'replies']
            )

            if not response.data:
                return []

            # Parse tweets
            tweets = []
            for tweet in response.data:
                tweets.append({
                    'post_id': str(tweet.id),
                    'platform': 'twitter',
                    'author': username,
                    'content': tweet.text,
                    'url': f"https://twitter.com/{username}/status/{tweet.id}",
                    'engagement_score': self._calculate_engagement(tweet.public_metrics),
                    'posted_at': tweet.created_at
                })

            return tweets

        except Exception as e:
            logger.error(f"Error getting user tweets for {username}: {e}")
            return []

    @staticmethod
    def _calculate_engagement(metrics: Dict) -> int:
        """
        Calculate engagement score from tweet metrics.

        Args:
            metrics: Public metrics dictionary

        Returns:
            Engagement score
        """
        if not metrics:
            return 0

        # Weighted engagement score
        likes = metrics.get('like_count', 0)
        retweets = metrics.get('retweet_count', 0)
        replies = metrics.get('reply_count', 0)
        quotes = metrics.get('quote_count', 0)

        # Retweets and replies weighted higher
        score = likes + (retweets * 3) + (replies * 2) + (quotes * 2)
        return score

    def extract_keywords_from_question(self, question: str) -> List[str]:
        """
        Extract relevant search keywords from a Polymarket question.

        Args:
            question: Market question

        Returns:
            List of search keywords
        """
        # Simple keyword extraction (could be enhanced with NLP)
        # Remove common words and extract key terms
        common_words = {'will', 'the', 'be', 'in', 'to', 'of', 'and', 'or', 'a', 'an', 'by', 'on'}

        words = question.lower().replace('?', '').split()
        keywords = [w for w in words if len(w) > 3 and w not in common_words]

        # Take top 3-5 most relevant keywords
        return keywords[:5]
