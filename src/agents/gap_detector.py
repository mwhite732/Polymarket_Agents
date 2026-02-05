"""Gap Detection Agent - Identifies pricing inefficiencies in prediction markets."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from crewai import Agent, Task
from sqlalchemy import func

from ..config import get_settings, get_llm
from ..database import get_db_manager
from ..database.models import Contract, DetectedGap, SentimentAnalysis, HistoricalOdds
from ..utils.logger import get_logger

logger = get_logger(__name__)


class GapDetectionAgent:
    """
    Agent responsible for detecting pricing gaps in prediction markets.

    Identifies four types of gaps:
    1. Sentiment-Probability Mismatches: Market odds don't align with social sentiment
    2. Information Asymmetry: New information not yet reflected in prices
    3. Cross-Market Arbitrage: Pricing inconsistencies (future enhancement)
    4. Historical Pattern Deviations: Unusual odds movements compared to history
    """

    def __init__(self):
        """Initialize Gap Detection Agent."""
        self.settings = get_settings()
        self.db_manager = get_db_manager()

        # Initialize LLM (OpenAI or Ollama based on config)
        self.llm = get_llm()

        logger.info(f"Gap Detection Agent initialized with {self.settings.llm_provider}")

    def create_crewai_agent(self) -> Agent:
        """
        Create CrewAI agent definition.

        Returns:
            CrewAI Agent instance
        """
        return Agent(
            role='Market Inefficiency Detector',
            goal='Identify pricing gaps and inefficiencies in prediction markets',
            backstory="""You are an expert quantitative analyst specializing in prediction
            markets. You excel at identifying mispricings by analyzing sentiment data,
            historical patterns, and market dynamics. You provide clear reasoning for
            each identified opportunity.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    def detect_sentiment_mismatch(self, contract_id: str) -> Optional[Dict]:
        """
        Detect sentiment-probability mismatch for a contract.

        Args:
            contract_id: Contract UUID as string

        Returns:
            Gap dictionary if detected, None otherwise
        """
        try:
            with self.db_manager.get_session() as session:
                # Get contract
                contract = session.query(Contract).filter(
                    Contract.id == UUID(contract_id)
                ).first()

                if not contract or not contract.current_yes_odds:
                    return None

                # Get sentiment data
                sentiment_analyses = session.query(SentimentAnalysis).filter(
                    SentimentAnalysis.contract_id == UUID(contract_id)
                ).all()

                if not sentiment_analyses or len(sentiment_analyses) < 5:
                    # Need sufficient data
                    return None

                # Calculate aggregate sentiment
                avg_sentiment = sum(float(s.sentiment_score) for s in sentiment_analyses) / len(sentiment_analyses)
                positive_count = sum(1 for s in sentiment_analyses if s.sentiment_label == 'positive')
                positive_ratio = positive_count / len(sentiment_analyses)

                # Convert sentiment to implied probability
                # Sentiment of +1 (very bullish) → ~90% probability
                # Sentiment of 0 (neutral) → ~50% probability
                # Sentiment of -1 (very bearish) → ~10% probability
                implied_prob = 0.5 + (avg_sentiment * 0.4)  # Maps -1..1 to 0.1..0.9
                implied_odds = Decimal(str(round(implied_prob, 4)))

                # Current market odds
                market_odds = float(contract.current_yes_odds)

                # Calculate gap
                gap_size = abs(implied_prob - market_odds)

                # Check if gap exceeds threshold
                if gap_size < self.settings.gap_detection_threshold:
                    return None

                # Determine direction and confidence
                if implied_prob > market_odds:
                    direction = "bullish"
                    edge = (implied_prob - market_odds) * 100
                else:
                    direction = "bearish"
                    edge = (market_odds - implied_prob) * 100

                # Calculate confidence score (0-100)
                # Factors: gap size, data volume, sentiment consistency
                gap_factor = min(gap_size / 0.3, 1.0) * 40  # Max 40 points
                volume_factor = min(len(sentiment_analyses) / 50, 1.0) * 30  # Max 30 points
                consistency_factor = abs(positive_ratio - 0.5) * 2 * 30  # Max 30 points

                confidence = int(gap_factor + volume_factor + consistency_factor)

                # Generate explanation using LLM
                explanation = self._generate_gap_explanation(
                    contract=contract,
                    gap_type="sentiment_mismatch",
                    market_odds=market_odds,
                    implied_odds=float(implied_odds),
                    sentiment_data={
                        'avg_sentiment': avg_sentiment,
                        'positive_ratio': positive_ratio,
                        'total_posts': len(sentiment_analyses),
                        'direction': direction
                    }
                )

                return {
                    'contract_id': contract_id,
                    'gap_type': 'sentiment_mismatch',
                    'confidence_score': confidence,
                    'explanation': explanation,
                    'market_odds': contract.current_yes_odds,
                    'implied_odds': implied_odds,
                    'edge_percentage': Decimal(str(round(edge, 2))),
                    'evidence': {
                        'avg_sentiment': round(avg_sentiment, 3),
                        'positive_ratio': round(positive_ratio, 3),
                        'total_posts': len(sentiment_analyses),
                        'direction': direction,
                        'gap_size': round(gap_size, 3)
                    }
                }

        except Exception as e:
            logger.error(f"Error detecting sentiment mismatch: {e}")
            return None

    def detect_information_asymmetry(self, contract_id: str) -> Optional[Dict]:
        """
        Detect information asymmetry gaps (recent news not reflected in odds).

        Args:
            contract_id: Contract UUID as string

        Returns:
            Gap dictionary if detected, None otherwise
        """
        try:
            with self.db_manager.get_session() as session:
                # Get contract
                contract = session.query(Contract).filter(
                    Contract.id == UUID(contract_id)
                ).first()

                if not contract:
                    return None

                # Get very recent sentiment (last 3 hours) vs older (3-6 hours ago)
                now = datetime.utcnow()
                recent_cutoff = now - timedelta(hours=3)
                older_cutoff = now - timedelta(hours=6)

                # Recent sentiment
                recent_sentiment = session.query(SentimentAnalysis).join(
                    SentimentAnalysis.post
                ).filter(
                    SentimentAnalysis.contract_id == UUID(contract_id),
                    SentimentAnalysis.analyzed_at >= recent_cutoff
                ).all()

                # Older sentiment
                older_sentiment = session.query(SentimentAnalysis).join(
                    SentimentAnalysis.post
                ).filter(
                    SentimentAnalysis.contract_id == UUID(contract_id),
                    SentimentAnalysis.analyzed_at >= older_cutoff,
                    SentimentAnalysis.analyzed_at < recent_cutoff
                ).all()

                if len(recent_sentiment) < 5 or len(older_sentiment) < 5:
                    return None

                # Calculate sentiment shifts
                recent_avg = sum(float(s.sentiment_score) for s in recent_sentiment) / len(recent_sentiment)
                older_avg = sum(float(s.sentiment_score) for s in older_sentiment) / len(older_sentiment)

                sentiment_shift = recent_avg - older_avg

                # Check if there's a significant shift
                if abs(sentiment_shift) < 0.3:  # Threshold for significant shift
                    return None

                # Check if odds have moved accordingly
                historical_odds = session.query(HistoricalOdds).filter(
                    HistoricalOdds.contract_id == UUID(contract_id)
                ).order_by(HistoricalOdds.recorded_at.desc()).limit(10).all()

                if len(historical_odds) < 2:
                    return None

                recent_odds = float(historical_odds[0].yes_odds)
                older_odds = float(historical_odds[-1].yes_odds)
                odds_movement = recent_odds - older_odds

                # Information asymmetry: sentiment shifted but odds haven't
                # Positive sentiment shift → odds should increase
                # Negative sentiment shift → odds should decrease
                expected_direction = 1 if sentiment_shift > 0 else -1
                actual_direction = 1 if odds_movement > 0 else -1 if odds_movement < 0 else 0

                if expected_direction == actual_direction and abs(odds_movement) > 0.05:
                    # Odds already moved - no asymmetry
                    return None

                # Calculate confidence
                shift_magnitude = abs(sentiment_shift)
                confidence = int(min(shift_magnitude / 0.5, 1.0) * 60 + 20)

                # Generate explanation
                explanation = self._generate_gap_explanation(
                    contract=contract,
                    gap_type="info_asymmetry",
                    market_odds=recent_odds,
                    implied_odds=None,
                    sentiment_data={
                        'recent_avg': recent_avg,
                        'older_avg': older_avg,
                        'shift': sentiment_shift,
                        'recent_posts': len(recent_sentiment)
                    }
                )

                return {
                    'contract_id': contract_id,
                    'gap_type': 'info_asymmetry',
                    'confidence_score': confidence,
                    'explanation': explanation,
                    'market_odds': contract.current_yes_odds,
                    'implied_odds': None,
                    'edge_percentage': Decimal(str(round(abs(sentiment_shift) * 50, 2))),
                    'evidence': {
                        'sentiment_shift': round(sentiment_shift, 3),
                        'recent_avg_sentiment': round(recent_avg, 3),
                        'older_avg_sentiment': round(older_avg, 3),
                        'recent_posts': len(recent_sentiment),
                        'odds_movement': round(odds_movement, 4)
                    }
                }

        except Exception as e:
            logger.error(f"Error detecting information asymmetry: {e}")
            return None

    def detect_pattern_deviation(self, contract_id: str) -> Optional[Dict]:
        """
        Detect historical pattern deviations.

        Args:
            contract_id: Contract UUID as string

        Returns:
            Gap dictionary if detected, None otherwise
        """
        try:
            with self.db_manager.get_session() as session:
                # Get contract
                contract = session.query(Contract).filter(
                    Contract.id == UUID(contract_id)
                ).first()

                if not contract or not self.settings.enable_historical_analysis:
                    return None

                # Get historical odds
                historical = session.query(HistoricalOdds).filter(
                    HistoricalOdds.contract_id == UUID(contract_id)
                ).order_by(HistoricalOdds.recorded_at.asc()).all()

                if len(historical) < 10:
                    # Need sufficient history
                    return None

                # Calculate volatility and trends
                odds_values = [float(h.yes_odds) for h in historical]
                current_odds = odds_values[-1]

                # Calculate moving average and standard deviation
                avg_odds = sum(odds_values) / len(odds_values)
                variance = sum((x - avg_odds) ** 2 for x in odds_values) / len(odds_values)
                std_dev = variance ** 0.5

                # Check for unusual deviations
                z_score = (current_odds - avg_odds) / std_dev if std_dev > 0 else 0

                if abs(z_score) < 2.0:  # Not unusual enough
                    return None

                # Calculate confidence based on deviation magnitude
                confidence = int(min(abs(z_score) / 3.0, 1.0) * 70 + 10)

                # Generate explanation
                explanation = self._generate_gap_explanation(
                    contract=contract,
                    gap_type="pattern_deviation",
                    market_odds=current_odds,
                    implied_odds=avg_odds,
                    sentiment_data={
                        'z_score': z_score,
                        'std_dev': std_dev,
                        'avg_odds': avg_odds
                    }
                )

                return {
                    'contract_id': contract_id,
                    'gap_type': 'pattern_deviation',
                    'confidence_score': confidence,
                    'explanation': explanation,
                    'market_odds': contract.current_yes_odds,
                    'implied_odds': Decimal(str(round(avg_odds, 4))),
                    'edge_percentage': Decimal(str(round(abs(current_odds - avg_odds) * 100, 2))),
                    'evidence': {
                        'z_score': round(z_score, 2),
                        'std_dev': round(std_dev, 4),
                        'avg_odds': round(avg_odds, 4),
                        'historical_points': len(historical)
                    }
                }

        except Exception as e:
            logger.error(f"Error detecting pattern deviation: {e}")
            return None

    def _generate_gap_explanation(
        self,
        contract: Contract,
        gap_type: str,
        market_odds: float,
        implied_odds: Optional[float],
        sentiment_data: Dict
    ) -> str:
        """
        Generate human-readable explanation using LLM.

        Args:
            contract: Contract object
            gap_type: Type of gap detected
            market_odds: Current market odds
            implied_odds: Implied odds from analysis
            sentiment_data: Supporting sentiment data

        Returns:
            Explanation string
        """
        try:
            prompt = f"""Generate a clear, concise explanation for a pricing gap in a prediction market.

Market Question: "{contract.question}"
Current Market Odds: {market_odds:.1%} YES
Gap Type: {gap_type}
{f"Implied Odds: {implied_odds:.1%}" if implied_odds else ""}

Supporting Data: {json.dumps(sentiment_data, indent=2)}

Provide a 2-3 sentence explanation that:
1. Describes the gap clearly
2. Explains why it exists
3. Notes the direction (bullish/bearish opportunity)

Be specific and actionable. Do not use phrases like "might" or "could be" - be direct.
"""

            response = self.llm.invoke(prompt)
            explanation = response.content.strip()

            return explanation

        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            # Fallback explanation
            return f"{gap_type.replace('_', ' ').title()} detected. Market odds at {market_odds:.1%}."

    def detect_all_gaps(self, contract_id: str) -> List[Dict]:
        """
        Run all gap detection methods for a contract.

        Args:
            contract_id: Contract UUID as string

        Returns:
            List of detected gaps
        """
        gaps = []

        # Sentiment mismatch
        gap = self.detect_sentiment_mismatch(contract_id)
        if gap:
            gaps.append(gap)

        # Information asymmetry
        gap = self.detect_information_asymmetry(contract_id)
        if gap:
            gaps.append(gap)

        # Pattern deviation
        gap = self.detect_pattern_deviation(contract_id)
        if gap:
            gaps.append(gap)

        # TODO: Cross-market arbitrage (future enhancement)

        return gaps

    def analyze_all_contracts(self) -> List[Dict]:
        """
        Analyze all active contracts for gaps.

        Returns:
            List of all detected gaps
        """
        logger.info("Starting gap detection for all contracts...")

        all_gaps = []

        try:
            with self.db_manager.get_session() as session:
                # Get active contracts
                contracts = session.query(Contract).filter(
                    Contract.active == True
                ).all()

                for contract in contracts:
                    logger.info(f"Analyzing gaps for: {contract.question[:50]}...")

                    gaps = self.detect_all_gaps(str(contract.id))

                    # Store gaps in database
                    for gap in gaps:
                        if gap['confidence_score'] >= self.settings.min_confidence_score:
                            detected_gap = DetectedGap(
                                contract_id=UUID(gap['contract_id']),
                                gap_type=gap['gap_type'],
                                confidence_score=gap['confidence_score'],
                                explanation=gap['explanation'],
                                evidence=gap['evidence'],
                                market_odds=gap['market_odds'],
                                implied_odds=gap.get('implied_odds'),
                                edge_percentage=gap['edge_percentage']
                            )
                            session.add(detected_gap)
                            all_gaps.append(gap)

                session.commit()

        except Exception as e:
            logger.error(f"Error analyzing contracts: {e}")

        logger.info(f"Gap detection complete: {len(all_gaps)} gaps found")
        return all_gaps

    def create_detection_task(self) -> Task:
        """
        Create CrewAI task for gap detection.

        Returns:
            CrewAI Task instance
        """
        return Task(
            description="""Detect pricing gaps and inefficiencies in prediction markets:
            1. Identify sentiment-probability mismatches
            2. Detect information asymmetry (recent news not reflected)
            3. Find historical pattern deviations
            4. Calculate confidence scores (0-100) for each gap
            5. Generate clear explanations with supporting evidence
            6. Store detected gaps in database
            """,
            agent=self.create_crewai_agent(),
            expected_output="List of detected pricing gaps with confidence scores and explanations"
        )

    def run(self) -> List[Dict]:
        """
        Execute gap detection workflow.

        Returns:
            List of detected gaps
        """
        logger.info("=== Starting Gap Detection Agent ===")

        gaps = self.analyze_all_contracts()

        logger.info(f"Gap detection complete: {len(gaps)} opportunities identified")

        return gaps
