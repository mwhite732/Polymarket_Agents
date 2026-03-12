#!/usr/bin/env python3
"""
Quick start script for Polymarket Gap Detector.

Usage:
    python run.py              # Interactive mode (run cycle, prompt for next)
    python run.py continuous   # Auto-loop mode (no prompts, runs forever)
    python run.py demo         # Run demo mode (single cycle, exit)
    python run.py once         # Run once and exit (no prompt)
    python run.py dashboard    # Start FastAPI dashboard only
    python run.py monitor      # Run monitoring only (no dashboard)
    python run.py test         # Test configuration
"""

import sys
import threading
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))


def test_configuration():
    """Test system configuration and database connection."""
    print("Testing configuration...")
    print("-" * 80)

    # Test imports
    try:
        from src.config import get_settings
        from src.database import init_database
        print("[OK] Imports successful")
    except ImportError as e:
        print(f"[FAIL] Import error: {e}")
        print("\nPlease run: pip install -r requirements.txt")
        return False

    # Test configuration
    try:
        settings = get_settings()
        settings.validate_required_services()
        print("[OK] Configuration valid")
        print(f"  - LLM Provider: {settings.llm_provider}")
        print(f"  - Twitter enabled: {settings.enable_twitter}")
        print(f"  - Reddit enabled: {settings.enable_reddit}")
    except Exception as e:
        print(f"[FAIL] Configuration error: {e}")
        print("\nPlease check your .env file")
        return False

    # Test database
    try:
        db = init_database()
        if db.test_connection():
            print("[OK] Database connection successful")
            stats = db.get_stats()
            print(f"  - Contracts: {stats.get('contracts', 0)}")
            print(f"  - Social Posts: {stats.get('social_posts', 0)}")
            print(f"  - Detected Gaps: {stats.get('detected_gaps', 0)}")
        else:
            print("[FAIL] Database connection failed")
            return False
    except Exception as e:
        print(f"[FAIL] Database error: {e}")
        print("\nPlease check your DATABASE_URL and PostgreSQL installation")
        return False

    print("-" * 80)
    print("[OK] All tests passed! System is ready.")
    return True


def start_dashboard_thread(port=8000):
    """Start the dashboard in a background thread."""
    try:
        from src.dashboard.app import app
        import uvicorn

        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=port,
            log_level="warning",  # Quiet -- monitoring logs are the main output
        )
        server = uvicorn.Server(config)
        server.run()
    except Exception as e:
        print(f"[WARNING] Dashboard failed to start: {e}")
        print("  Monitoring will continue without the dashboard.")


def get_cycle_summary():
    """Fetch a summary of the current database state for the end-of-cycle report."""
    try:
        from src.database import get_db_manager
        db = get_db_manager()
        stats = db.get_stats()
        return stats
    except Exception:
        return {}


def print_cycle_summary(results, stats, cycle_num):
    """Print a nice summary after a cycle completes."""
    print()
    print("=" * 60)
    print(f"  CYCLE #{cycle_num} COMPLETE")
    print("=" * 60)

    if results.get('success'):
        duration = results.get('duration_seconds', 0)
        mins = int(duration // 60)
        secs = int(duration % 60)

        print(f"  Status:      OK")
        print(f"  Duration:    {mins}m {secs}s")
        print()

        # Collection stats
        coll = results.get('collection', {})
        print(f"  Contracts:   {coll.get('contracts_collected', 0)}")
        print(f"  Posts:       {coll.get('social_posts', 0)}")

        # Sentiment stats
        sent = results.get('sentiment', {})
        print(f"  Sentiments:  {sent.get('contracts_analyzed', 0)} contracts analyzed")

        # Gap stats
        gaps = results.get('gaps', {})
        total_gaps = gaps.get('total_gaps', 0)
        print(f"  Gaps Found:  {total_gaps}")

        if gaps.get('by_type'):
            for gtype, count in gaps['by_type'].items():
                print(f"    - {gtype}: {count}")

        # Backtest stats
        bt = results.get('backtest', {})
        if bt:
            print(f"  Backtest:    {bt.get('total_predictions', 0)} predictions, "
                  f"win rate {bt.get('win_rate', 0):.1%}")

        # DB totals
        if stats:
            print()
            print(f"  --- Database Totals ---")
            print(f"  Total Contracts:  {stats.get('contracts', 0)}")
            print(f"  Total Posts:      {stats.get('social_posts', 0)}")
            print(f"  Total Sentiments: {stats.get('sentiment_analyses', 0)}")
            print(f"  Total Gaps:       {stats.get('detected_gaps', 0)}")
    else:
        print(f"  Status:  ERRORS")
        for err in results.get('errors', []):
            print(f"    - {err}")

    print("=" * 60)


def run_interactive(dashboard_port=8000):
    """
    Interactive mode: run one cycle, show summary, prompt for another.
    Dashboard stays alive between cycles.
    """
    from src.main import PolymarketGapDetector

    print()
    print("=" * 60)
    print("  POLYMARKET GAP DETECTOR - Interactive Mode")
    print("=" * 60)
    print(f"  Dashboard: http://localhost:{dashboard_port}")
    print("  Press Ctrl+C at any time to exit")
    print("  Dashboard will stay alive between cycles")
    print("=" * 60)
    print()

    detector = PolymarketGapDetector()
    cycle_num = 0

    while True:
        cycle_num += 1

        # Run a cycle
        results = detector.run_single_cycle()

        # Get DB stats for summary
        stats = get_cycle_summary()

        # Print summary
        print_cycle_summary(results, stats, cycle_num)

        # Prompt the user
        print()
        print("  Dashboard is still live at http://localhost:{}"
              .format(dashboard_port))
        print()

        try:
            answer = input("  Run another cycle? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            answer = "n"

        if answer in ("y", "yes"):
            print("\n  Starting next cycle...\n")
            continue
        else:
            print()
            print("  Monitoring stopped. Dashboard is still running.")
            print(f"  Browse results at http://localhost:{dashboard_port}")
            print("  Press Ctrl+C to exit completely.")
            print()

            # Keep the main thread alive so the dashboard daemon thread stays up
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n\nExiting...")
                break


def main():
    """Main entry point."""
    mode = sys.argv[1] if len(sys.argv) > 1 else "interactive"

    if mode == "test":
        success = test_configuration()
        sys.exit(0 if success else 1)

    if mode == "dashboard":
        from src.dashboard.app import start_dashboard
        start_dashboard()
        return

    # Start dashboard for all modes except "monitor" and "test"
    if mode in ("interactive", "continuous", "once", "demo"):
        dashboard_port = 8000
        print(f"\n[*] Starting dashboard at http://localhost:{dashboard_port}")
        print("[*] Starting monitoring system...\n")

        dashboard_thread = threading.Thread(
            target=start_dashboard_thread,
            args=(dashboard_port,),
            daemon=True,  # Dies when main thread exits
        )
        dashboard_thread.start()
        time.sleep(1)  # Let uvicorn bind before logs start flooding

    # For "monitor" mode: skip dashboard
    if mode == "monitor":
        print("\n[*] Starting monitoring only (no dashboard)...\n")

    # Interactive mode (default)
    if mode == "interactive":
        try:
            run_interactive()
        except KeyboardInterrupt:
            print("\n\nExiting...")
        return

    # Import and run main system for other modes
    try:
        from src.main import main as run_main
        run_main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
