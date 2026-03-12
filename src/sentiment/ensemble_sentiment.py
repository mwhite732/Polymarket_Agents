"""Ensemble sentiment combining LLM scores with lexicon models (VADER + TextBlob)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Lazy-load heavy imports
_vader = None
_textblob_available = False


def _get_vader():
    global _vader
    if _vader is None:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            _vader = SentimentIntensityAnalyzer()
        except ImportError:
            logger.warning("vaderSentiment not installed. pip install vaderSentiment")
            _vader = False
    return _vader if _vader is not False else None


def _get_textblob_polarity(text: str) -> Optional[float]:
    try:
        from textblob import TextBlob
        return TextBlob(text).sentiment.polarity
    except ImportError:
        logger.debug("textblob not installed")
        return None
    except Exception:
        return None


class EnsembleSentiment:
    """
    Combines LLM sentiment scores with lexicon-based models for stability.

    VADER + TextBlob run locally (sub-millisecond), adding negligible latency.
    The ensemble reduces noise from unreliable LLM parses.
    """

    def __init__(self):
        # Pre-warm VADER on first use
        self._vader = _get_vader()
        logger.info("Ensemble Sentiment initialized")

    def score(self, text: str) -> Dict:
        """
        Compute lexicon sentiment scores for a piece of text.

        Args:
            text: Input text to analyze

        Returns:
            Dict with vader_score, textblob_score, combined_score (all -1 to 1)
        """
        vader_score = None
        textblob_score = None

        # VADER
        vader = _get_vader()
        if vader:
            try:
                vader_score = vader.polarity_scores(text)['compound']
            except Exception:
                pass

        # TextBlob
        textblob_score = _get_textblob_polarity(text)

        # Combined lexicon score
        scores = [s for s in [vader_score, textblob_score] if s is not None]
        combined = sum(scores) / len(scores) if scores else 0.0

        return {
            'vader_score': round(vader_score, 3) if vader_score is not None else None,
            'textblob_score': round(textblob_score, 3) if textblob_score is not None else None,
            'combined_score': round(combined, 3),
        }

    @staticmethod
    def ensemble_score(
        llm_score: float,
        vader_score: Optional[float] = None,
        textblob_score: Optional[float] = None,
        llm_weight: float = 0.5
    ) -> float:
        """
        Compute weighted ensemble of LLM + lexicon scores.

        Args:
            llm_score: LLM sentiment score (-1 to 1)
            vader_score: VADER compound score (-1 to 1)
            textblob_score: TextBlob polarity (-1 to 1)
            llm_weight: Weight for LLM score (remainder split among lexicon scores)

        Returns:
            Ensemble score (-1 to 1)
        """
        scores = [(llm_score, llm_weight)]

        lexicon_scores = [s for s in [vader_score, textblob_score] if s is not None]
        if lexicon_scores:
            lexicon_weight = (1 - llm_weight) / len(lexicon_scores)
            for s in lexicon_scores:
                scores.append((s, lexicon_weight))
        else:
            # No lexicon scores available, LLM gets full weight
            scores = [(llm_score, 1.0)]

        ensemble = sum(s * w for s, w in scores)
        return round(max(-1.0, min(1.0, ensemble)), 3)

    def compute_rolling_sentiment(
        self,
        contract_id: str,
        window_hours: int = 24
    ) -> Dict:
        """
        Compute rolling sentiment aggregate for a contract from the database.

        Args:
            contract_id: Contract UUID string
            window_hours: Hours to look back (6, 12, or 24)

        Returns:
            Dict with aggregate stats
        """
        try:
            from ..database import get_db_manager
            from ..database.models import SentimentAnalysis, SentimentSnapshot

            db_manager = get_db_manager()
            cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

            with db_manager.get_session() as session:
                analyses = session.query(SentimentAnalysis).filter(
                    SentimentAnalysis.contract_id == UUID(contract_id),
                    SentimentAnalysis.analyzed_at >= cutoff
                ).all()

                if not analyses:
                    return {'available': False, 'window_hours': window_hours}

                # Use ensemble_score if available, fall back to sentiment_score
                scores = []
                for a in analyses:
                    if a.ensemble_score is not None:
                        scores.append(float(a.ensemble_score))
                    elif a.sentiment_score is not None:
                        scores.append(float(a.sentiment_score))

                if not scores:
                    return {'available': False, 'window_hours': window_hours}

                positive_count = sum(1 for a in analyses if a.sentiment_label == 'positive')
                avg = sum(scores) / len(scores)
                trend = scores[-1] - scores[0] if len(scores) >= 2 else 0.0

                # Store snapshot
                snapshot = SentimentSnapshot(
                    contract_id=UUID(contract_id),
                    window_hours=window_hours,
                    avg_score=Decimal(str(round(avg, 3))),
                    post_count=len(scores),
                    positive_ratio=Decimal(str(round(positive_count / len(analyses), 3))),
                    sentiment_trend=Decimal(str(round(trend, 3)))
                )
                session.add(snapshot)

                return {
                    'available': True,
                    'window_hours': window_hours,
                    'data_points': len(scores),
                    'mean_sentiment': round(avg, 3),
                    'sentiment_trend': round(trend, 3),
                    'positive_ratio': round(positive_count / len(analyses), 3),
                }

        except Exception as e:
            logger.error(f"Rolling sentiment error: {e}")
            return {'available': False, 'window_hours': window_hours, 'error': str(e)}
