"""Reporting Agent - Ranks and formats pricing gap opportunities."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from crewai import Agent, Task
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from ..config import get_settings
from ..database import get_db_manager
from ..database.models import Contract, DetectedGap
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ReportingAgent:
    """
    Agent responsible for ranking and reporting detected pricing gaps.

    Responsibilities:
    - Rank gaps by confidence score and potential edge
    - Format output for console display
    - Generate clear, actionable reports
    - Present evidence and reasoning
    """

    def __init__(self):
        """Initialize Reporting Agent."""
        self.settings = get_settings()
        self.db_manager = get_db_manager()
        self.console = Console(width=self.settings.console_output_width)

        logger.info("Reporting Agent initialized")

    def create_crewai_agent(self) -> Agent:
        """
        Create CrewAI agent definition.

        Returns:
            CrewAI Agent instance
        """
        return Agent(
            role='Market Intelligence Reporter',
            goal='Present pricing gaps in a clear, actionable format',
            backstory="""You are an expert at synthesizing complex market data into
            actionable insights. You excel at prioritizing opportunities and presenting
            them in a way that decision-makers can quickly understand and act upon.""",
            verbose=True,
            allow_delegation=False
        )

    def fetch_recent_gaps(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Fetch recently detected gaps from database.

        Args:
            limit: Maximum number of gaps to fetch

        Returns:
            List of gap dictionaries with contract information
        """
        limit = limit or self.settings.max_gaps_to_display

        try:
            with self.db_manager.get_session() as session:
                # Get recent unresolved gaps. One row per (contract_id, gap_type) - latest only.
                subq = (
                    session.query(
                        DetectedGap.id,
                        func.row_number().over(
                            partition_by=[DetectedGap.contract_id, DetectedGap.gap_type],
                            order_by=DetectedGap.detected_at.desc()
                        ).label('rn')
                    ).filter(
                        DetectedGap.resolved == False,
                        DetectedGap.confidence_score >= self.settings.min_confidence_score
                    )
                ).subquery()

                gap_ids = [
                    r[0] for r in
                    session.query(subq.c.id).filter(subq.c.rn == 1).limit(limit * 2).all()
                ]

                if not gap_ids:
                    return []

                gaps = (
                    session.query(DetectedGap)
                    .options(joinedload(DetectedGap.contract))
                    .filter(DetectedGap.id.in_(gap_ids))
                    .order_by(DetectedGap.confidence_score.desc(), DetectedGap.detected_at.desc())
                    .limit(limit)
                    .all()
                )

                # Format gaps with contract information
                result = []
                for gap in gaps:
                    contract = gap.contract

                    if contract:
                        result.append({
                            'id': str(gap.id),
                            'contract_id': str(gap.contract_id),
                            'question': contract.question,
                            'gap_type': gap.gap_type,
                            'confidence_score': gap.confidence_score,
                            'explanation': gap.explanation,
                            'evidence': gap.evidence,
                            'market_odds': float(gap.market_odds) if gap.market_odds else None,
                            'implied_odds': float(gap.implied_odds) if gap.implied_odds else None,
                            'edge_percentage': float(gap.edge_percentage) if gap.edge_percentage else None,
                            'detected_at': gap.detected_at.isoformat(),
                            'category': contract.category,
                            'end_date': contract.end_date.isoformat() if contract.end_date else None
                        })

                return result

        except Exception as e:
            logger.error(f"Error fetching gaps: {e}")
            return []

    def rank_gaps(self, gaps: List[Dict]) -> List[Dict]:
        """
        Rank gaps by confidence and potential edge.

        Args:
            gaps: List of gap dictionaries

        Returns:
            Sorted list of gaps with rank numbers
        """
        # Calculate composite score: confidence * edge_factor
        for gap in gaps:
            confidence = gap['confidence_score']
            edge = gap.get('edge_percentage', 0)

            # Composite score favors high confidence and high edge
            composite_score = (confidence * 0.7) + (min(edge, 20) * 1.5)
            gap['composite_score'] = composite_score

        # Sort by composite score
        ranked = sorted(gaps, key=lambda x: x['composite_score'], reverse=True)

        # Add rank numbers
        for i, gap in enumerate(ranked, 1):
            gap['rank'] = i

        return ranked

    def format_gap_type(self, gap_type: str) -> str:
        """
        Format gap type for display.

        Args:
            gap_type: Raw gap type identifier

        Returns:
            Formatted gap type string
        """
        type_map = {
            'sentiment_mismatch': 'Sentiment-Probability Mismatch',
            'info_asymmetry': 'Information Asymmetry',
            'arbitrage': 'Cross-Market Arbitrage',
            'pattern_deviation': 'Historical Pattern Deviation'
        }
        return type_map.get(gap_type, gap_type.replace('_', ' ').title())

    def format_evidence(self, evidence: Dict) -> List[str]:
        """
        Format evidence dictionary into readable bullet points.

        Args:
            evidence: Evidence dictionary

        Returns:
            List of formatted evidence strings
        """
        if not evidence:
            return []

        bullets = []

        # Format based on available data
        if 'avg_sentiment' in evidence:
            sentiment = evidence['avg_sentiment']
            sentiment_pct = (sentiment + 1) / 2 * 100  # Convert -1..1 to 0..100
            bullets.append(f"Average sentiment: {sentiment_pct:.0f}% positive (score: {sentiment:+.2f})")

        if 'positive_ratio' in evidence:
            ratio = evidence['positive_ratio']
            bullets.append(f"Positive posts: {ratio:.1%} ({evidence.get('total_posts', 0)} total)")

        if 'sentiment_shift' in evidence:
            shift = evidence['sentiment_shift']
            direction = "more bullish" if shift > 0 else "more bearish"
            bullets.append(f"Recent sentiment shift: {abs(shift):.2f} {direction}")

        if 'z_score' in evidence:
            z = evidence['z_score']
            bullets.append(f"Statistical deviation: {abs(z):.1f} standard deviations")

        if 'odds_movement' in evidence:
            movement = evidence['odds_movement']
            if abs(movement) < 0.01:
                bullets.append(f"Market odds: unchanged (potential lag)")
            else:
                direction = "increased" if movement > 0 else "decreased"
                bullets.append(f"Market odds: {direction} by {abs(movement):.2%}")

        return bullets

    def print_console_report(self, gaps: List[Dict]):
        """
        Print formatted report to console using Rich library.

        Args:
            gaps: List of ranked gap dictionaries
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Header
        header = Text()
        header.append(f"[{timestamp}] ", style="dim")
        header.append("POLYMARKET PRICING GAPS", style="bold cyan")
        header.append(" - Real-time Analysis", style="dim")

        self.console.print()
        self.console.print(header, justify="center")
        self.console.print("=" * self.settings.console_output_width, style="dim")
        self.console.print()

        if not gaps:
            self.console.print(
                Panel(
                    "[yellow]No pricing gaps detected above confidence threshold.[/yellow]",
                    title="Status",
                    border_style="yellow"
                )
            )
            return

        # Display each gap
        for gap in gaps[:self.settings.max_gaps_to_display]:
            self._print_gap_panel(gap)

        # Summary
        self.console.print()
        self.console.print(f"[dim]Showing top {min(len(gaps), self.settings.max_gaps_to_display)} "
                          f"of {len(gaps)} detected gaps[/dim]")
        self.console.print()

    def _print_gap_panel(self, gap: Dict):
        """
        Print a single gap as a formatted panel.

        Args:
            gap: Gap dictionary
        """
        rank = gap['rank']
        confidence = gap['confidence_score']
        gap_type = self.format_gap_type(gap['gap_type'])

        # Build panel content
        content = Text()

        # Contract question
        content.append("Contract: ", style="bold")
        content.append(f"{gap['question']}\n\n", style="white")

        # Odds information
        if gap['market_odds']:
            yes_pct = gap['market_odds'] * 100
            no_pct = (1 - gap['market_odds']) * 100
            content.append("Current Odds: ", style="bold")
            content.append(f"YES {yes_pct:.1f}% / NO {no_pct:.1f}%\n", style="cyan")

        if gap['implied_odds']:
            implied_pct = gap['implied_odds'] * 100
            content.append("Implied Odds: ", style="bold")
            content.append(f"{implied_pct:.1f}%\n", style="green")

        if gap['edge_percentage']:
            content.append("Potential Edge: ", style="bold")
            content.append(f"{gap['edge_percentage']:.1f}%\n", style="yellow")

        content.append("\n")

        # Explanation
        content.append("Analysis:\n", style="bold")
        content.append(f"{gap['explanation']}\n\n", style="white")

        # Evidence
        content.append("Evidence:\n", style="bold")
        evidence_bullets = self.format_evidence(gap.get('evidence', {}))
        for bullet in evidence_bullets:
            content.append(f"  • {bullet}\n", style="dim")

        # Metadata
        content.append("\n")
        content.append(f"Category: {gap.get('category', 'Unknown')} | ", style="dim")
        content.append(f"Detected: {gap['detected_at'][:19]}", style="dim")

        # Panel styling based on confidence
        if confidence >= 80:
            border_style = "bold green"
            title_style = "bold white on green"
        elif confidence >= 70:
            border_style = "green"
            title_style = "white on green"
        elif confidence >= 60:
            border_style = "yellow"
            title_style = "black on yellow"
        else:
            border_style = "dim"
            title_style = "white on dim"

        # Create panel
        panel = Panel(
            content,
            title=f"[{title_style}] RANK #{rank} - Confidence: {confidence}/100 [/{title_style}]",
            subtitle=f"[dim]{gap_type}[/dim]",
            border_style=border_style,
            padding=(1, 2)
        )

        self.console.print(panel)
        self.console.print()

    def generate_table_report(self, gaps: List[Dict]) -> Table:
        """
        Generate a table view of gaps.

        Args:
            gaps: List of ranked gap dictionaries

        Returns:
            Rich Table object
        """
        table = Table(title="Pricing Gaps Summary", show_header=True, header_style="bold cyan")

        table.add_column("Rank", justify="center", style="cyan", width=6)
        table.add_column("Confidence", justify="center", style="green", width=10)
        table.add_column("Type", justify="left", style="yellow", width=20)
        table.add_column("Contract", justify="left", style="white", width=50)
        table.add_column("Edge", justify="right", style="magenta", width=8)

        for gap in gaps[:self.settings.max_gaps_to_display]:
            table.add_row(
                f"#{gap['rank']}",
                f"{gap['confidence_score']}/100",
                self.format_gap_type(gap['gap_type']),
                gap['question'][:47] + "..." if len(gap['question']) > 50 else gap['question'],
                f"{gap.get('edge_percentage', 0):.1f}%"
            )

        return table

    def create_reporting_task(self) -> Task:
        """
        Create CrewAI task for reporting.

        Returns:
            CrewAI Task instance
        """
        return Task(
            description="""Generate comprehensive report of pricing gaps:
            1. Fetch recently detected gaps from database
            2. Rank by confidence score and potential edge
            3. Format gaps for console display
            4. Present evidence and reasoning clearly
            5. Highlight top opportunities
            """,
            agent=self.create_crewai_agent(),
            expected_output="Formatted console report of top pricing gaps"
        )

    def run(self) -> List[Dict]:
        """
        Execute reporting workflow.

        Returns:
            List of ranked gaps
        """
        logger.info("=== Starting Reporting Agent ===")

        # Fetch gaps
        gaps = self.fetch_recent_gaps()

        if not gaps:
            logger.info("No gaps to report")
            self.print_console_report([])
            return []

        # Rank gaps
        ranked_gaps = self.rank_gaps(gaps)

        # Print report
        self.print_console_report(ranked_gaps)

        logger.info(f"Report generated: {len(ranked_gaps)} gaps")

        return ranked_gaps
