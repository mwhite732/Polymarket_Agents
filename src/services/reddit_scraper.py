"""Reddit scraping and API integration with ethical data collection."""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from ratelimit import limits, sleep_and_retry

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    print("WARNING: praw not installed. Reddit integration will be limited.")

from ..config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class RedditScraper:
    """
    Ethical Reddit data collector using official API.

    Respects Reddit API terms of service:
    - Uses PRAW (Python Reddit API Wrapper)
    - Implements proper rate limiting
    - Identifies with appropriate user agent
    - No unauthorized scraping
    """

    def __init__(self):
        """Initialize Reddit scraper."""
        self.settings = get_settings()
        self.reddit = None
        self.enabled = self.settings.enable_reddit and self.settings.has_reddit_credentials

        if self.enabled and PRAW_AVAILABLE:
            self._initialize_client()
        else:
            logger.warning("Reddit scraper disabled (no credentials or praw not installed)")

    def _initialize_client(self):
        """Initialize Reddit API client."""
        try:
            self.reddit = praw.Reddit(
                client_id=self.settings.reddit_client_id,
                client_secret=self.settings.reddit_client_secret,
                user_agent=self.settings.reddit_user_agent,
                read_only=True  # We only need read access
            )

            # Test authentication
            _ = self.reddit.user.me()
            logger.info("Reddit API client initialized (read-only mode)")

        except Exception as e:
            logger.error(f"Error initializing Reddit client: {e}")
            self.enabled = False

    @sleep_and_retry
    @limits(calls=60, period=60)  # 60 calls per minute
    def search_posts(
        self,
        query: str,
        subreddits: Optional[List[str]] = None,
        max_results: int = 100,
        hours_back: int = 24,
        sort: str = 'relevance'
    ) -> List[Dict]:
        """
        Search Reddit posts matching query.

        Args:
            query: Search query
            subreddits: List of subreddit names to search (None for all)
            max_results: Maximum posts to return
            hours_back: How many hours back to search
            sort: Sort method ('relevance', 'hot', 'top', 'new')

        Returns:
            List of post dictionaries
        """
        if not self.enabled or not self.reddit:
            logger.warning("Reddit search skipped (not enabled)")
            return []

        try:
            # Determine search scope
            if subreddits:
                subreddit_str = '+'.join(subreddits)
                search_scope = self.reddit.subreddit(subreddit_str)
            else:
                search_scope = self.reddit.subreddit('all')

            # Calculate time limit
            time_limit = datetime.utcnow() - timedelta(hours=hours_back)
            time_limit_unix = int(time_limit.timestamp())

            logger.info(f"Searching Reddit for: {query} in {subreddits or 'all'}")

            # Search posts
            posts = []
            search_results = search_scope.search(
                query,
                sort=sort,
                time_filter='week',  # API time filter
                limit=max_results
            )

            for submission in search_results:
                # Filter by our time limit
                post_time = datetime.fromtimestamp(submission.created_utc)
                if post_time < time_limit:
                    continue

                # Skip deleted/removed posts
                if submission.removed_by_category or submission.selftext == '[removed]':
                    continue

                posts.append({
                    'post_id': f"reddit_{submission.id}",
                    'platform': 'reddit',
                    'author': str(submission.author) if submission.author else '[deleted]',
                    'content': self._get_post_content(submission),
                    'url': f"https://reddit.com{submission.permalink}",
                    'engagement_score': self._calculate_engagement(submission),
                    'posted_at': post_time,
                    'raw_data': {
                        'subreddit': submission.subreddit.display_name,
                        'upvote_ratio': submission.upvote_ratio,
                        'num_comments': submission.num_comments,
                        'score': submission.score
                    }
                })

            logger.info(f"Found {len(posts)} Reddit posts for query: {query}")
            return posts

        except Exception as e:
            logger.error(f"Error searching Reddit posts: {e}")
            return []

    def search_subreddit_posts(
        self,
        subreddit_name: str,
        query: Optional[str] = None,
        max_results: int = 50,
        hours_back: int = 24,
        sort: str = 'hot'
    ) -> List[Dict]:
        """
        Get posts from a specific subreddit.

        Args:
            subreddit_name: Subreddit name (without r/)
            query: Optional search query within subreddit
            max_results: Maximum posts to return
            hours_back: Hours to look back
            sort: Sort method ('hot', 'new', 'top', 'rising')

        Returns:
            List of post dictionaries
        """
        if not self.enabled or not self.reddit:
            logger.warning("Reddit subreddit search skipped (not enabled)")
            return []

        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            time_limit = datetime.utcnow() - timedelta(hours=hours_back)

            posts = []

            # Get posts based on sort method
            if query:
                # Search within subreddit
                submissions = subreddit.search(query, limit=max_results)
            else:
                # Get posts by sort method
                if sort == 'hot':
                    submissions = subreddit.hot(limit=max_results)
                elif sort == 'new':
                    submissions = subreddit.new(limit=max_results)
                elif sort == 'top':
                    submissions = subreddit.top(time_filter='day', limit=max_results)
                elif sort == 'rising':
                    submissions = subreddit.rising(limit=max_results)
                else:
                    submissions = subreddit.hot(limit=max_results)

            for submission in submissions:
                post_time = datetime.fromtimestamp(submission.created_utc)
                if post_time < time_limit:
                    continue

                if submission.removed_by_category or submission.selftext == '[removed]':
                    continue

                posts.append({
                    'post_id': f"reddit_{submission.id}",
                    'platform': 'reddit',
                    'author': str(submission.author) if submission.author else '[deleted]',
                    'content': self._get_post_content(submission),
                    'url': f"https://reddit.com{submission.permalink}",
                    'engagement_score': self._calculate_engagement(submission),
                    'posted_at': post_time,
                    'raw_data': {
                        'subreddit': subreddit_name,
                        'upvote_ratio': submission.upvote_ratio,
                        'num_comments': submission.num_comments,
                        'score': submission.score
                    }
                })

            return posts

        except Exception as e:
            logger.error(f"Error searching subreddit {subreddit_name}: {e}")
            return []

    def search_multiple_subreddits(
        self,
        subreddits: List[str],
        query: str,
        max_per_subreddit: int = 25,
        hours_back: int = 24
    ) -> List[Dict]:
        """
        Search multiple subreddits for relevant posts.

        Args:
            subreddits: List of subreddit names
            query: Search query
            max_per_subreddit: Max posts per subreddit
            hours_back: Hours to look back

        Returns:
            Combined list of posts
        """
        all_posts = []
        seen_ids = set()

        for subreddit in subreddits:
            posts = self.search_subreddit_posts(
                subreddit_name=subreddit,
                query=query,
                max_results=max_per_subreddit,
                hours_back=hours_back
            )

            # Deduplicate
            for post in posts:
                if post['post_id'] not in seen_ids:
                    all_posts.append(post)
                    seen_ids.add(post['post_id'])

            # Rate limiting between subreddits
            time.sleep(1)

        logger.info(f"Collected {len(all_posts)} posts from {len(subreddits)} subreddits")
        return all_posts

    @staticmethod
    def _get_post_content(submission) -> str:
        """
        Extract content from Reddit submission.

        Args:
            submission: PRAW submission object

        Returns:
            Post content (title + body if applicable)
        """
        content = submission.title

        # Add selftext if it's a text post
        if submission.selftext and submission.selftext not in ['', '[removed]', '[deleted]']:
            # Limit length to avoid huge posts
            body = submission.selftext[:1000]
            if len(submission.selftext) > 1000:
                body += "..."
            content = f"{content}\n\n{body}"

        return content

    @staticmethod
    def _calculate_engagement(submission) -> int:
        """
        Calculate engagement score from Reddit post metrics.

        Args:
            submission: PRAW submission object

        Returns:
            Engagement score
        """
        # Weighted engagement score
        # Upvotes (score) + comments weighted more
        score = submission.score
        comments = submission.num_comments * 2

        return max(score + comments, 0)

    def get_relevant_subreddits(self, topic: str) -> List[str]:
        """
        Get list of relevant subreddits for a topic.

        Args:
            topic: Topic to find subreddits for

        Returns:
            List of subreddit names
        """
        # Predefined subreddits for common prediction market topics
        topic_subreddits = {
            'politics': ['politics', 'worldnews', 'PoliticalDiscussion', 'geopolitics'],
            'crypto': ['cryptocurrency', 'bitcoin', 'CryptoCurrency', 'ethfinance'],
            'sports': ['sports', 'nfl', 'nba', 'soccer', 'baseball'],
            'finance': ['wallstreetbets', 'stocks', 'investing', 'Economics'],
            'tech': ['technology', 'tech', 'programming', 'Futurology'],
            'entertainment': ['movies', 'television', 'entertainment', 'Music'],
            'default': ['all', 'news', 'worldnews']
        }

        # Simple keyword matching
        topic_lower = topic.lower()
        for key, subreddits in topic_subreddits.items():
            if key in topic_lower:
                return subreddits

        return topic_subreddits['default']

    def extract_keywords_from_question(self, question: str) -> List[str]:
        """
        Extract relevant search keywords from a Polymarket question.

        Args:
            question: Market question

        Returns:
            List of search keywords
        """
        # Simple keyword extraction
        common_words = {'will', 'the', 'be', 'in', 'to', 'of', 'and', 'or', 'a', 'an', 'by', 'on'}

        words = question.lower().replace('?', '').split()
        keywords = [w for w in words if len(w) > 3 and w not in common_words]

        # Take top 3-5 most relevant keywords
        return keywords[:5]
