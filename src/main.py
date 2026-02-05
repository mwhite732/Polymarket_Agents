"""Main orchestration system for Polymarket Pricing Gap Detection."""

import asyncio
import time
from datetime import datetime
from pathlib import Path

from crewai import Crew, Process

from .agents import (
    DataCollectionAgent,
    SentimentAnalysisAgent,
    GapDetectionAgent,
    ReportingAgent
)
from .config import get_settings
from .database import init_database
from .utils.logger import setup_logger, get_logger


class PolymarketGapDetector:
    """
    Main orchestration class for the multi-agent pricing gap detection system.

    Coordinates four specialized agents:
    1. Data Collection Agent - Fetches market and social media data
    2. Sentiment Analysis Agent - Analyzes social sentiment
    3. Gap Detection Agent - Identifies pricing inefficiencies
    4. Reporting Agent - Ranks and formats results
    """

    def __init__(self):
        """Initialize the gap detection system."""
        # Setup logger
        self.logger = setup_logger()
        self.logger.info("Initializing Polymarket Gap Detector...")

        # Load settings
        self.settings = get_settings()

        # Initialize database
        try:
            self.db_manager = init_database()
            self.logger.info("Database connection established")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise

        # Initialize agents
        self.data_collector = DataCollectionAgent()
        self.sentiment_analyzer = SentimentAnalysisAgent()
        self.gap_detector = GapDetectionAgent()
        self.reporter = ReportingAgent()

        self.logger.info("All agents initialized successfully")

    def run_single_cycle(self) -> dict:
        """
        Execute one complete analysis cycle.

        Returns:
            Dictionary with cycle results
        """
        cycle_start = time.time()
        self.logger.info("=" * 80)
        self.logger.info("STARTING NEW ANALYSIS CYCLE")
        self.logger.info("=" * 80)

        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'success': False,
            'errors': []
        }

        try:
            # Step 1: Data Collection
            self.logger.info("\n[STEP 1/4] Data Collection")
            self.logger.info("-" * 80)
            collection_results = self.data_collector.run()
            results['collection'] = {
                'contracts_collected': len(collection_results.get('contracts', [])),
                'social_posts': sum(len(p) for p in collection_results.get('social_posts', {}).values())
            }
            self.logger.info(f"✓ Collected {results['collection']['contracts_collected']} contracts, "
                           f"{results['collection']['social_posts']} social posts")

            # Step 2: Sentiment Analysis
            self.logger.info("\n[STEP 2/4] Sentiment Analysis")
            self.logger.info("-" * 80)
            sentiment_results = self.sentiment_analyzer.run()
            results['sentiment'] = {
                'contracts_analyzed': len(sentiment_results)
            }
            self.logger.info(f"✓ Analyzed sentiment for {len(sentiment_results)} contracts")

            # Step 3: Gap Detection
            self.logger.info("\n[STEP 3/4] Gap Detection")
            self.logger.info("-" * 80)
            gaps = self.gap_detector.run()
            results['gaps'] = {
                'total_gaps': len(gaps),
                'by_type': {}
            }

            # Count gaps by type
            for gap in gaps:
                gap_type = gap.get('gap_type', 'unknown')
                results['gaps']['by_type'][gap_type] = results['gaps']['by_type'].get(gap_type, 0) + 1

            self.logger.info(f"✓ Detected {len(gaps)} pricing gaps")

            # Step 4: Reporting
            self.logger.info("\n[STEP 4/4] Generating Report")
            self.logger.info("-" * 80)
            ranked_gaps = self.reporter.run()
            results['report'] = {
                'gaps_reported': len(ranked_gaps)
            }

            results['success'] = True
            cycle_duration = time.time() - cycle_start
            results['duration_seconds'] = round(cycle_duration, 2)

            self.logger.info("\n" + "=" * 80)
            self.logger.info(f"CYCLE COMPLETE - Duration: {cycle_duration:.2f}s")
            self.logger.info("=" * 80)

        except Exception as e:
            self.logger.error(f"Error during analysis cycle: {e}", exc_info=True)
            results['errors'].append(str(e))

        return results

    def run_continuous(self):
        """
        Run continuous monitoring with polling intervals.

        This is the main entry point for production use.
        """
        self.logger.info("Starting continuous monitoring mode")
        self.logger.info(f"Polling interval: {self.settings.polling_interval} seconds")

        cycle_count = 0

        try:
            while True:
                cycle_count += 1
                self.logger.info(f"\n{'='*80}")
                self.logger.info(f"CYCLE #{cycle_count}")
                self.logger.info(f"{'='*80}\n")

                # Run analysis cycle
                results = self.run_single_cycle()

                if results['success']:
                    self.logger.info(f"✓ Cycle #{cycle_count} completed successfully")
                else:
                    self.logger.error(f"✗ Cycle #{cycle_count} completed with errors")

                # Wait for next cycle
                self.logger.info(f"\nWaiting {self.settings.polling_interval} seconds until next cycle...")
                time.sleep(self.settings.polling_interval)

        except KeyboardInterrupt:
            self.logger.info("\n\nShutdown signal received. Stopping gracefully...")
            self.cleanup()
        except Exception as e:
            self.logger.error(f"Fatal error in continuous mode: {e}", exc_info=True)
            self.cleanup()
            raise

    def cleanup(self):
        """Cleanup resources on shutdown."""
        self.logger.info("Cleaning up resources...")

        # Close database connections
        if hasattr(self, 'db_manager'):
            self.db_manager.close()
            self.logger.info("Database connections closed")

        self.logger.info("Cleanup complete. Goodbye!")

    def run_demo(self):
        """
        Run a single demonstration cycle with detailed output.

        Useful for testing and demonstrations.
        """
        self.logger.info("=" * 80)
        self.logger.info("RUNNING DEMONSTRATION MODE")
        self.logger.info("=" * 80)
        self.logger.info("")

        results = self.run_single_cycle()

        if results['success']:
            self.logger.info("\n✓ Demo completed successfully!")
            self.logger.info(f"   - Collected {results['collection']['contracts_collected']} contracts")
            self.logger.info(f"   - Analyzed {results['collection']['social_posts']} social posts")
            self.logger.info(f"   - Detected {results['gaps']['total_gaps']} pricing gaps")
            self.logger.info(f"   - Duration: {results['duration_seconds']}s")
        else:
            self.logger.error("\n✗ Demo completed with errors")
            for error in results.get('errors', []):
                self.logger.error(f"   - {error}")


def main():
    """Main entry point."""
    import sys

    # Create logs directory if it doesn't exist
    Path("logs").mkdir(exist_ok=True)

    # Parse command line arguments
    mode = sys.argv[1] if len(sys.argv) > 1 else "continuous"

    try:
        detector = PolymarketGapDetector()

        if mode == "demo":
            detector.run_demo()
        elif mode == "once":
            detector.run_single_cycle()
        else:
            detector.run_continuous()

    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
