"""Backtesting engine for measuring gap detection performance."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from ..database import get_db_manager
from ..database.models import DetectedGap, BacktestResult
from ..utils.logger import get_logger

logger = get_logger(__name__)


class Backtester:
    """
    Backtests gap detection by analyzing resolved gaps.

    Answers: "If I had acted on every gap with confidence > threshold, what's my win rate?"
    Requires resolved gaps (resolved=True, was_correct set) in the detected_gaps table.
    """

    def __init__(self):
        self.db_manager = get_db_manager()

    def run_backtest(
        self,
        confidence_threshold: int = 60,
        gap_type: Optional[str] = None,
        top_k: int = 50
    ) -> Dict:
        """
        Run backtest at a given confidence threshold.

        Args:
            confidence_threshold: Minimum confidence score (0-100)
            gap_type: Filter to specific gap type, or None for all
            top_k: Max gaps to evaluate

        Returns:
            Dict with win_rate, sample_size, avg_edge, by_gap_type breakdown
        """
        try:
            with self.db_manager.get_session() as session:
                query = session.query(DetectedGap).filter(
                    DetectedGap.resolved == True,
                    DetectedGap.was_correct != None,
                    DetectedGap.confidence_score >= confidence_threshold,
                )

                if gap_type:
                    query = query.filter(DetectedGap.gap_type == gap_type)

                gaps = query.order_by(DetectedGap.confidence_score.desc()).limit(top_k).all()

                if not gaps:
                    return {
                        'message': 'No resolved gaps above threshold',
                        'threshold': confidence_threshold,
                        'gap_type': gap_type,
                        'sample_size': 0
                    }

                total = len(gaps)
                wins = sum(1 for g in gaps if g.was_correct)
                win_rate = wins / total

                # Average realized edge
                edges = [float(g.realized_edge) for g in gaps if g.realized_edge is not None]
                avg_edge = sum(edges) / len(edges) if edges else None

                # Expected ROI (simplified binary market)
                expected_roi = (win_rate * 2) - 1

                # Breakdown by gap type
                by_type = {}
                for g in gaps:
                    gt = g.gap_type
                    if gt not in by_type:
                        by_type[gt] = {'count': 0, 'wins': 0, 'total_edge': 0.0, 'edge_count': 0}
                    by_type[gt]['count'] += 1
                    if g.was_correct:
                        by_type[gt]['wins'] += 1
                    if g.realized_edge is not None:
                        by_type[gt]['total_edge'] += float(g.realized_edge)
                        by_type[gt]['edge_count'] += 1

                for gt, data in by_type.items():
                    data['win_rate'] = round(data['wins'] / data['count'], 4) if data['count'] > 0 else 0
                    data['avg_edge'] = round(data['total_edge'] / data['edge_count'], 4) \
                        if data['edge_count'] > 0 else None
                    del data['total_edge']
                    del data['edge_count']

                result = {
                    'threshold': confidence_threshold,
                    'gap_type': gap_type,
                    'sample_size': total,
                    'wins': wins,
                    'win_rate': round(win_rate, 4),
                    'expected_roi': round(expected_roi, 4),
                    'avg_edge': round(avg_edge, 4) if avg_edge is not None else None,
                    'by_gap_type': by_type,
                }

                # Store result
                backtest = BacktestResult(
                    gap_type=gap_type,
                    threshold=Decimal(str(confidence_threshold)),
                    total_predictions=total,
                    correct_predictions=wins,
                    win_rate=Decimal(str(round(win_rate, 4))),
                    avg_edge=Decimal(str(round(avg_edge, 4))) if avg_edge is not None else None,
                    expected_roi=Decimal(str(round(expected_roi, 4))),
                    result_metadata=by_type,
                )
                session.add(backtest)

                logger.info(f"Backtest: threshold={confidence_threshold}, "
                           f"n={total}, win_rate={win_rate:.1%}")
                return result

        except Exception as e:
            logger.error(f"Backtest error: {e}")
            return {'error': str(e)}

    def tune_thresholds(self) -> List[Dict]:
        """
        Run backtest at multiple thresholds to find optimal cutoff.

        Returns:
            List of results sorted by expected ROI (best first)
        """
        results = []
        for threshold in [40, 50, 55, 60, 65, 70, 75, 80]:
            r = self.run_backtest(confidence_threshold=threshold)
            if 'win_rate' in r:
                results.append({
                    'threshold': threshold,
                    'win_rate': r['win_rate'],
                    'expected_roi': r['expected_roi'],
                    'sample_size': r['sample_size'],
                })

        results.sort(key=lambda x: x['expected_roi'], reverse=True)

        if results:
            best = results[0]
            logger.info(f"Best threshold: {best['threshold']} "
                       f"(win_rate={best['win_rate']:.1%}, ROI={best['expected_roi']:.1%})")

        return results
