"""Dynamic confidence scoring with social data weighting."""

from typing import Dict, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ConfidenceScorer:
    """
    Computes dynamic confidence scores for detected gaps.

    Key behavior:
    - When social data is sparse, down-weight social signals and up-weight price-only signals
    - Arbitrage gaps (price-only) are unaffected by social data availability
    - Historical pattern gaps partially depend on social confirmation
    - Standard analysis gaps are most affected by social availability
    """

    def score(
        self,
        gap_type: str,
        gap_size: float,
        data_volume: int,
        sentiment_consistency: float,
        social_sources_count: int = 0,
        contract_features: Dict = None,
    ) -> int:
        """
        Compute confidence score (0-100) for a detected gap.

        Args:
            gap_type: 'sentiment_mismatch' | 'info_asymmetry' | 'arbitrage' | 'pattern_deviation'
            gap_size: Size of the detected gap (0-1 range)
            data_volume: Number of data points supporting the gap
            sentiment_consistency: How consistent the sentiment signal is (0-1)
            social_sources_count: Number of distinct social platforms with data
            contract_features: Dict from ContractFeatureEngine

        Returns:
            Confidence score 0-100
        """
        contract_features = contract_features or {}

        if gap_type == 'arbitrage':
            return self._score_arbitrage(gap_size, data_volume, contract_features)
        elif gap_type == 'pattern_deviation':
            return self._score_pattern(gap_size, data_volume, social_sources_count, contract_features)
        else:
            return self._score_analysis(
                gap_size, data_volume, sentiment_consistency,
                social_sources_count, contract_features
            )

    def _score_arbitrage(self, gap_size: float, data_volume: int, features: Dict) -> int:
        """Arbitrage is price-only — social data irrelevant."""
        # Gap size factor (up to 50 points)
        gap_factor = min(gap_size / 0.20, 1.0) * 50

        # Data quality factor (more markets = higher confidence, up to 30 points)
        data_factor = min(data_volume / 3, 1.0) * 30

        # Base confidence (20 points)
        base = 20

        # Near resolution boost
        if features.get('is_near_resolution'):
            base += 5

        return min(100, max(0, int(gap_factor + data_factor + base)))

    def _score_pattern(
        self, gap_size: float, data_volume: int,
        social_sources_count: int, features: Dict
    ) -> int:
        """Historical pattern — partially depends on social confirmation."""
        # Gap size factor (z-score based, up to 40 points)
        gap_factor = min(gap_size / 3.0, 1.0) * 40

        # Historical data volume (up to 30 points)
        data_factor = min(data_volume / 30, 1.0) * 30

        # Social confirmation (partial weight, up to 20 points)
        if social_sources_count >= 2:
            social_factor = 20
        elif social_sources_count == 1:
            social_factor = 10
        else:
            social_factor = 0  # No penalty, just no bonus

        # Base
        base = 10

        return min(100, max(0, int(gap_factor + data_factor + social_factor + base)))

    def _score_analysis(
        self, gap_size: float, data_volume: int,
        sentiment_consistency: float, social_sources_count: int,
        features: Dict
    ) -> int:
        """Standard sentiment/info gap — most affected by social data."""
        # Gap size factor (up to 40 points)
        gap_factor = min(gap_size / 0.15, 1.0) * 40

        # Data volume factor (up to 25 points, tuned for realistic volumes)
        volume_factor = min(data_volume / 15, 1.0) * 25

        # Sentiment consistency factor (up to 25 points)
        consistency_factor = sentiment_consistency * 25

        # Social data richness multiplier
        if social_sources_count == 0:
            # Heavy down-weight: no social confirmation
            multiplier = 0.5
        elif social_sources_count == 1:
            multiplier = 0.75
        else:
            multiplier = 1.0

        raw_score = gap_factor + volume_factor + consistency_factor

        # Apply social multiplier
        adjusted = raw_score * multiplier

        # Feature adjustments
        if features.get('is_near_resolution'):
            adjusted *= 1.1  # Near resolution = more predictable
        if features.get('price_volatility_24h', 0) > 0.15:
            adjusted *= 0.9  # High volatility = less confident

        return min(100, max(0, int(adjusted)))
