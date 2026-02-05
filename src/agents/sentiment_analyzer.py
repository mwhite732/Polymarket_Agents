"""Sentiment Analysis Agent - Analyzes social media sentiment using LLM."""

import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from crewai import Agent, Task

from ..config import get_settings, get_llm
from ..database import get_db_manager
from ..database.models import SocialPost, SentimentAnalysis, Contract
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SentimentAnalysisAgent:
    """
    Agent responsible for analyzing sentiment of social media posts.

    Responsibilities:
    - Perform sentiment analysis on collected social posts
    - Generate sentiment scores (-1 to +1) and labels
    - Extract key topics and themes
    - Aggregate sentiment per contract
    - Store analysis results in database
    """

    def __init__(self):
        """Initialize Sentiment Analysis Agent."""
        self.settings = get_settings()
        self.db_manager = get_db_manager()

        # Initialize LLM (OpenAI or Ollama based on config)
        self.llm = get_llm()

        logger.info(f"Sentiment Analysis Agent initialized with {self.settings.llm_provider}")

    def create_crewai_agent(self) -> Agent:
        """
        Create CrewAI agent definition.

        Returns:
            CrewAI Agent instance
        """
        return Agent(
            role='Sentiment Analysis Specialist',
            goal='Accurately analyze sentiment and extract insights from social media content',
            backstory="""You are an expert in natural language processing and sentiment analysis.
            You excel at understanding nuanced opinions in social media posts, identifying
            bullish and bearish signals, and aggregating sentiment across multiple sources.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    def analyze_posts_batch(self, post_ids: List[str], contract_id: str) -> List[Dict]:
        """
        Analyze sentiment for a batch of posts.

        Args:
            post_ids: List of social post IDs (UUIDs as strings)
            contract_id: Associated contract ID (UUID as string)

        Returns:
            List of sentiment analysis results
        """
        results = []

        try:
            with self.db_manager.get_session() as session:
                # Fetch posts
                posts = session.query(SocialPost).filter(
                    SocialPost.id.in_([UUID(pid) for pid in post_ids])
                ).all()

                # Batch posts for efficiency
                batch_size = self.settings.sentiment_batch_size
                for i in range(0, len(posts), batch_size):
                    batch = posts[i:i + batch_size]

                    # Analyze each post in batch
                    for post in batch:
                        sentiment = self._analyze_single_post(post.content)

                        if sentiment:
                            # Store in database
                            analysis = SentimentAnalysis(
                                post_id=post.id,
                                contract_id=UUID(contract_id),
                                sentiment_score=sentiment['score'],
                                sentiment_label=sentiment['label'],
                                confidence=sentiment['confidence'],
                                topics=sentiment.get('topics', [])
                            )
                            session.add(analysis)
                            results.append(sentiment)

                session.commit()

        except Exception as e:
            logger.error(f"Error analyzing posts batch: {e}")

        return results

    def _analyze_single_post(self, content: str) -> Optional[Dict]:
        """
        Analyze sentiment of a single post using LLM.

        Args:
            content: Post content text

        Returns:
            Sentiment analysis result dictionary
        """
        try:
            # Create prompt for sentiment analysis
            prompt = f"""Analyze the sentiment of this social media post in the context of prediction markets.

Post: "{content}"

Provide a JSON response with:
1. sentiment_score: A number from -1.0 (very negative/bearish) to +1.0 (very positive/bullish)
2. sentiment_label: One of "positive", "negative", or "neutral"
3. confidence: Your confidence in this analysis (0.0 to 1.0)
4. topics: A list of 2-3 key topics or themes mentioned (e.g., ["bitcoin", "regulation"])

Consider:
- Bullish signals: optimism, positive predictions, supportive language
- Bearish signals: pessimism, negative predictions, critical language
- Neutral: factual statements, questions, unclear sentiment

Respond with ONLY valid JSON, no additional text.
"""

            # Call LLM
            response = self.llm.invoke(prompt)
            result_text = response.content.strip()

            # Parse JSON response
            # Remove markdown code blocks if present
            if result_text.startswith('```'):
                result_text = result_text.split('```')[1]
                if result_text.startswith('json'):
                    result_text = result_text[4:]
                result_text = result_text.strip()

            sentiment = json.loads(result_text)

            # Validate and normalize
            return {
                'score': Decimal(str(max(-1.0, min(1.0, float(sentiment['sentiment_score']))))),
                'label': sentiment['sentiment_label'].lower(),
                'confidence': Decimal(str(max(0.0, min(1.0, float(sentiment['confidence']))))),
                'topics': sentiment.get('topics', [])[:5]  # Limit topics
            }

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing LLM JSON response: {e}")
            return None
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return None

    def analyze_contract_sentiment(self, contract_id: str) -> Dict:
        """
        Analyze and aggregate sentiment for a specific contract.

        Args:
            contract_id: Contract UUID as string

        Returns:
            Aggregated sentiment dictionary
        """
        logger.info(f"Analyzing sentiment for contract {contract_id}")

        try:
            with self.db_manager.get_session() as session:
                # Get contract
                contract = session.query(Contract).filter(
                    Contract.id == UUID(contract_id)
                ).first()

                if not contract:
                    logger.warning(f"Contract not found: {contract_id}")
                    return {}

                # Get recent social posts (last 24 hours)
                posts = session.query(SocialPost).filter(
                    SocialPost.related_contracts.contains([UUID(contract_id)])
                ).order_by(SocialPost.posted_at.desc()).limit(200).all()

                if not posts:
                    logger.info(f"No social posts found for contract {contract_id}")
                    return {
                        'contract_id': contract_id,
                        'total_posts': 0,
                        'avg_sentiment': 0.0,
                        'sentiment_distribution': {'positive': 0, 'negative': 0, 'neutral': 0}
                    }

                # Check which posts need analysis
                posts_to_analyze = []
                for post in posts:
                    existing = session.query(SentimentAnalysis).filter(
                        SentimentAnalysis.post_id == post.id,
                        SentimentAnalysis.contract_id == UUID(contract_id)
                    ).first()

                    if not existing:
                        posts_to_analyze.append(post)

                # Analyze new posts
                if posts_to_analyze:
                    logger.info(f"Analyzing {len(posts_to_analyze)} new posts...")
                    for post in posts_to_analyze:
                        sentiment = self._analyze_single_post(post.content)
                        if sentiment:
                            analysis = SentimentAnalysis(
                                post_id=post.id,
                                contract_id=UUID(contract_id),
                                sentiment_score=sentiment['score'],
                                sentiment_label=sentiment['label'],
                                confidence=sentiment['confidence'],
                                topics=sentiment.get('topics', [])
                            )
                            session.add(analysis)

                    session.commit()

                # Aggregate sentiment
                analyses = session.query(SentimentAnalysis).filter(
                    SentimentAnalysis.contract_id == UUID(contract_id)
                ).all()

                if not analyses:
                    return {
                        'contract_id': contract_id,
                        'total_posts': len(posts),
                        'avg_sentiment': 0.0,
                        'sentiment_distribution': {'positive': 0, 'negative': 0, 'neutral': 0}
                    }

                # Calculate aggregates
                total = len(analyses)
                avg_sentiment = sum(float(a.sentiment_score) for a in analyses) / total
                positive = sum(1 for a in analyses if a.sentiment_label == 'positive')
                negative = sum(1 for a in analyses if a.sentiment_label == 'negative')
                neutral = sum(1 for a in analyses if a.sentiment_label == 'neutral')

                # Extract common topics
                all_topics = []
                for a in analyses:
                    all_topics.extend(a.topics or [])
                topic_counts = {}
                for topic in all_topics:
                    topic_counts[topic] = topic_counts.get(topic, 0) + 1
                top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]

                return {
                    'contract_id': contract_id,
                    'question': contract.question,
                    'total_posts': len(posts),
                    'analyzed_posts': total,
                    'avg_sentiment': round(avg_sentiment, 3),
                    'sentiment_distribution': {
                        'positive': positive,
                        'negative': negative,
                        'neutral': neutral
                    },
                    'positive_ratio': round(positive / total, 3) if total > 0 else 0,
                    'top_topics': [{'topic': t[0], 'count': t[1]} for t in top_topics]
                }

        except Exception as e:
            logger.error(f"Error analyzing contract sentiment: {e}")
            return {}

    def analyze_all_active_contracts(self) -> List[Dict]:
        """
        Analyze sentiment for all active contracts.

        Returns:
            List of sentiment analysis results per contract
        """
        logger.info("Analyzing sentiment for all active contracts...")

        results = []

        try:
            with self.db_manager.get_session() as session:
                # Get active contracts
                contracts = session.query(Contract).filter(
                    Contract.active == True
                ).limit(self.settings.max_contracts_per_cycle).all()

                for contract in contracts:
                    sentiment = self.analyze_contract_sentiment(str(contract.id))
                    if sentiment:
                        results.append(sentiment)

        except Exception as e:
            logger.error(f"Error analyzing all contracts: {e}")

        logger.info(f"Sentiment analysis complete for {len(results)} contracts")
        return results

    def create_analysis_task(self) -> Task:
        """
        Create CrewAI task for sentiment analysis.

        Returns:
            CrewAI Task instance
        """
        return Task(
            description="""Perform comprehensive sentiment analysis on social media data:
            1. Analyze sentiment of collected social media posts
            2. Assign sentiment scores from -1 (bearish) to +1 (bullish)
            3. Classify sentiment as positive, negative, or neutral
            4. Extract key topics and themes
            5. Aggregate sentiment per contract
            6. Store analysis results in database
            """,
            agent=self.create_crewai_agent(),
            expected_output="Dictionary containing sentiment analysis results for all contracts"
        )

    def run(self) -> List[Dict]:
        """
        Execute sentiment analysis workflow.

        Returns:
            List of sentiment analysis results
        """
        logger.info("=== Starting Sentiment Analysis Agent ===")

        results = self.analyze_all_active_contracts()

        logger.info(f"Sentiment analysis complete: {len(results)} contracts analyzed")

        return results
