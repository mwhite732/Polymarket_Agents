"""Contract feature engineering for enriched gap detection and confidence scoring."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ContractFeatureEngine:
    """
    Computes enriched features for prediction market contracts.

    Features feed into gap detection and confidence scoring.
    All computation is local — no API calls.
    """

    @staticmethod
    def compute_features(contract: Dict, odds_history: List[Dict] = None) -> Dict:
        """
        Compute features from raw contract data and historical odds.

        Args:
            contract: Contract dict with keys: end_date, current_yes_odds, volume_24h, liquidity
            odds_history: List of dicts with 'yes_odds' and 'recorded_at' keys

        Returns:
            Dict of computed features
        """
        features = {}
        odds_history = odds_history or []

        # Time to expiry
        end_date = contract.get('end_date')
        if end_date:
            try:
                if isinstance(end_date, str):
                    end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                else:
                    end = end_date.replace(tzinfo=timezone.utc) if end_date.tzinfo is None else end_date
                now = datetime.now(timezone.utc)
                hours = max(0, (end - now).total_seconds() / 3600)
                features['time_to_expiry_hours'] = round(hours, 2)
                features['is_near_resolution'] = hours < 48
            except Exception:
                features['time_to_expiry_hours'] = None
                features['is_near_resolution'] = False
        else:
            features['time_to_expiry_hours'] = None
            features['is_near_resolution'] = False

        # Volume and liquidity
        features['volume_24h'] = float(contract.get('volume_24h') or 0)
        features['liquidity'] = float(contract.get('liquidity') or 0)

        # Spread (overround proxy)
        yes_odds = float(contract.get('current_yes_odds') or 0)
        no_odds = float(contract.get('current_no_odds') or 0)
        if yes_odds > 0 and no_odds > 0:
            features['spread'] = round(yes_odds + no_odds - 1.0, 4)
        else:
            features['spread'] = None

        # Historical odds-based features
        if odds_history and len(odds_history) >= 2:
            probs = [float(h.get('yes_odds', h.get('yes_probability', 0))) for h in odds_history]

            # Last price move
            features['last_price_move'] = round(probs[-1] - probs[-2], 4)

            # Volatility (std dev of odds)
            features['price_volatility_24h'] = round(float(np.std(probs[-48:])), 4) \
                if len(probs) >= 48 else round(float(np.std(probs)), 4)

            # Momentum (average direction of last 3 moves)
            if len(probs) >= 4:
                moves = [probs[i] - probs[i - 1] for i in range(-3, 0)]
                features['odds_momentum'] = round(float(np.mean(moves)), 4)
            else:
                features['odds_momentum'] = 0.0

            # Implied volatility proxy
            tte = features.get('time_to_expiry_hours')
            vol = features.get('price_volatility_24h', 0)
            if tte and tte > 0 and vol > 0:
                features['implied_volatility_proxy'] = round(
                    vol * np.sqrt(tte / 24), 4
                )
            else:
                features['implied_volatility_proxy'] = None

            # Volume momentum (if volume data available)
            volumes = [float(h.get('volume', 0)) for h in odds_history if h.get('volume')]
            if len(volumes) >= 2:
                avg_vol = np.mean(volumes[:-1])
                if avg_vol > 0:
                    features['volume_momentum'] = round((volumes[-1] - avg_vol) / avg_vol, 4)
                else:
                    features['volume_momentum'] = 0.0
            else:
                features['volume_momentum'] = 0.0
        else:
            features['last_price_move'] = 0.0
            features['price_volatility_24h'] = 0.0
            features['odds_momentum'] = 0.0
            features['implied_volatility_proxy'] = None
            features['volume_momentum'] = 0.0

        return features
