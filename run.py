#!/usr/bin/env python3
"""
Quick start script for Polymarket Gap Detector.

Usage:
    python run.py              # Run continuous monitoring
    python run.py demo         # Run demo mode (single cycle)
    python run.py once         # Run once and exit
    python run.py test         # Test configuration
"""

import sys
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


def main():
    """Main entry point."""
    mode = sys.argv[1] if len(sys.argv) > 1 else "continuous"

    if mode == "test":
        success = test_configuration()
        sys.exit(0 if success else 1)

    # Import and run main system
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
