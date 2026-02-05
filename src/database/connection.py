"""Database connection management."""

import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from .models import Base


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager.

        Args:
            database_url: PostgreSQL connection URL. If None, reads from settings.
        """
        # Import here to avoid circular imports
        if database_url is None:
            from ..config import get_settings
            settings = get_settings()
            self.database_url = settings.database_url
            pool_size = settings.db_pool_size
            max_overflow = settings.db_max_overflow
        else:
            self.database_url = database_url
            pool_size = int(os.getenv('DB_POOL_SIZE', '20'))
            max_overflow = int(os.getenv('DB_MAX_OVERFLOW', '0'))

        # Engine configuration for connection pooling
        self.engine = create_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,  # Verify connections before using
            echo=False  # Set to True for SQL query logging
        )

        # Session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        # Register event listeners
        self._register_event_listeners()

    def _register_event_listeners(self):
        """Register SQLAlchemy event listeners."""

        @event.listens_for(Engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            """Set connection parameters on connect."""
            # Set timezone to UTC
            with dbapi_conn.cursor() as cursor:
                cursor.execute("SET TIME ZONE 'UTC'")

    def create_tables(self):
        """Create all tables in the database."""
        Base.metadata.create_all(bind=self.engine)

    def drop_tables(self):
        """Drop all tables in the database. USE WITH CAUTION!"""
        Base.metadata.drop_all(bind=self.engine)

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.

        Yields:
            Session: SQLAlchemy session

        Example:
            with db_manager.get_session() as session:
                contracts = session.query(Contract).all()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def execute_sql(self, sql: str, params: Optional[dict] = None):
        """
        Execute raw SQL query.

        Args:
            sql: SQL query string
            params: Query parameters
        """
        with self.get_session() as session:
            result = session.execute(text(sql), params or {})
            return result.fetchall()

    def refresh_materialized_view(self, view_name: str = 'contract_sentiment_summary'):
        """
        Refresh a materialized view.

        Args:
            view_name: Name of the materialized view
        """
        sql = f"REFRESH MATERIALIZED VIEW {view_name}"
        with self.get_session() as session:
            session.execute(text(sql))

    def test_connection(self) -> bool:
        """
        Test database connection.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            print(f"Database connection test failed: {e}")
            return False

    def get_stats(self) -> dict:
        """
        Get database statistics.

        Returns:
            dict: Database statistics
        """
        with self.get_session() as session:
            stats = {}

            # Count records in each table
            from .models import (
                Contract, SocialPost, SentimentAnalysis,
                DetectedGap, SystemLog
            )

            stats['contracts'] = session.query(Contract).count()
            stats['active_contracts'] = session.query(Contract).filter(Contract.active == True).count()
            stats['social_posts'] = session.query(SocialPost).count()
            stats['sentiment_analyses'] = session.query(SentimentAnalysis).count()
            stats['detected_gaps'] = session.query(DetectedGap).count()
            stats['unresolved_gaps'] = session.query(DetectedGap).filter(DetectedGap.resolved == False).count()
            stats['system_logs'] = session.query(SystemLog).count()

            return stats

    def cleanup_old_data(self):
        """Execute database cleanup/archival."""
        sql = "SELECT archive_old_data()"
        with self.get_session() as session:
            session.execute(text(sql))

    def close(self):
        """Close all database connections."""
        self.engine.dispose()


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """
    Get or create global database manager instance.

    Returns:
        DatabaseManager: Singleton database manager
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def init_database(database_url: Optional[str] = None) -> DatabaseManager:
    """
    Initialize database and return manager.

    Args:
        database_url: PostgreSQL connection URL

    Returns:
        DatabaseManager: Initialized database manager
    """
    global _db_manager
    _db_manager = DatabaseManager(database_url)

    # Test connection
    if not _db_manager.test_connection():
        raise ConnectionError("Failed to connect to database")

    return _db_manager
