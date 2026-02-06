"""Configuration management using Pydantic settings."""

import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )

    # Database Configuration
    database_url: str = Field(
        default='postgresql://postgres:password@localhost:5432/polymarket_gaps',
        description='PostgreSQL connection URL'
    )
    db_pool_size: int = Field(default=20, description='Database connection pool size')
    db_max_overflow: int = Field(default=0, description='Database max overflow connections')

    # LLM Configuration
    llm_provider: str = Field(
        default='ollama',
        description='LLM provider: "openai" or "ollama" (free local models)'
    )

    # OpenAI API Configuration (only if llm_provider='openai')
    openai_api_key: Optional[str] = Field(default=None, description='OpenAI API key')
    openai_model: str = Field(
        default='gpt-4-turbo-preview',
        description='OpenAI model to use'
    )

    # Ollama Configuration (only if llm_provider='ollama')
    ollama_base_url: str = Field(
        default='http://localhost:11434',
        description='Ollama API base URL'
    )
    ollama_model: str = Field(
        default='llama3.1:8b',
        description='Ollama model to use (e.g., llama3.1:8b, mistral, phi3)'
    )

    # General LLM settings
    llm_temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description='LLM temperature for generation'
    )

    # Twitter/X API Configuration (Optional)
    twitter_api_key: Optional[str] = Field(default=None, description='Twitter API key')
    twitter_api_secret: Optional[str] = Field(default=None, description='Twitter API secret')
    twitter_bearer_token: Optional[str] = Field(default=None, description='Twitter bearer token')
    twitter_access_token: Optional[str] = Field(default=None, description='Twitter access token')
    twitter_access_secret: Optional[str] = Field(default=None, description='Twitter access secret')

    # Bluesky API Configuration (Free - just needs a Bluesky account)
    bluesky_handle: Optional[str] = Field(default=None, description='Bluesky handle (e.g. user.bsky.social)')
    bluesky_app_password: Optional[str] = Field(default=None, description='Bluesky app password (Settings > App Passwords)')

    # Reddit API Configuration (Optional)
    reddit_client_id: Optional[str] = Field(default=None, description='Reddit client ID')
    reddit_client_secret: Optional[str] = Field(default=None, description='Reddit client secret')
    reddit_user_agent: str = Field(
        default='PolymarketGapDetector/1.0',
        description='Reddit user agent'
    )

    # Polymarket API Configuration
    polymarket_api_url: str = Field(
        default='https://clob.polymarket.com',
        description='Polymarket CLOB API URL'
    )
    polymarket_gamma_api_url: str = Field(
        default='https://gamma-api.polymarket.com',
        description='Polymarket Gamma API URL'
    )
    polymarket_strapi_url: str = Field(
        default='https://strapi-matic.poly.market',
        description='Polymarket Strapi URL'
    )

    # System Configuration
    polling_interval: int = Field(
        default=300,
        ge=60,
        description='Seconds between data collection cycles'
    )
    max_contracts_per_cycle: int = Field(
        default=20,
        ge=1,
        description='Max contracts to analyze per cycle'
    )
    min_confidence_score: int = Field(
        default=60,
        ge=0,
        le=100,
        description='Minimum confidence to report a gap'
    )
    log_level: str = Field(
        default='INFO',
        description='Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)'
    )

    # Rate Limiting
    polymarket_rate_limit: int = Field(
        default=10,
        description='Polymarket API requests per minute'
    )
    twitter_rate_limit: int = Field(
        default=15,
        description='Twitter API requests per 15 minutes'
    )
    reddit_rate_limit: int = Field(
        default=60,
        description='Reddit API requests per minute'
    )
    bluesky_rate_limit: int = Field(
        default=30,
        description='Bluesky API requests per minute'
    )
    kalshi_rate_limit: int = Field(
        default=10,
        description='Kalshi API requests per second'
    )
    manifold_rate_limit: int = Field(
        default=30,
        description='Manifold Markets API requests per minute'
    )

    # Agent Configuration
    data_collection_lookback_hours: int = Field(
        default=6,
        ge=1,
        description='How far back to fetch social posts'
    )
    sentiment_batch_size: int = Field(
        default=50,
        ge=1,
        description='Posts per sentiment analysis batch'
    )
    gap_detection_threshold: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description='Minimum odds difference to flag'
    )
    arbitrage_min_edge: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description='Minimum cross-market price difference to flag as arbitrage'
    )

    # Feature Flags
    enable_twitter: bool = Field(default=True, description='Enable Twitter data collection')
    enable_reddit: bool = Field(default=True, description='Enable Reddit data collection')
    enable_bluesky: bool = Field(default=True, description='Enable Bluesky data collection (free, no API key)')
    enable_kalshi: bool = Field(default=True, description='Enable Kalshi cross-market comparison')
    enable_manifold: bool = Field(default=True, description='Enable Manifold Markets cross-market comparison')
    enable_historical_analysis: bool = Field(
        default=True,
        description='Enable historical pattern analysis'
    )
    enable_arbitrage_detection: bool = Field(
        default=True,
        description='Enable arbitrage detection'
    )

    # Output Configuration
    console_output_width: int = Field(
        default=120,
        ge=80,
        description='Console output width in characters'
    )
    max_gaps_to_display: int = Field(
        default=10,
        ge=1,
        description='Maximum gaps to display in output'
    )

    @property
    def has_twitter_credentials(self) -> bool:
        """Check if Twitter credentials are configured."""
        return bool(self.twitter_bearer_token or (
            self.twitter_api_key and
            self.twitter_api_secret and
            self.twitter_access_token and
            self.twitter_access_secret
        ))

    @property
    def has_reddit_credentials(self) -> bool:
        """Check if Reddit credentials are configured."""
        return bool(
            self.reddit_client_id and
            self.reddit_client_secret
        )

    @property
    def has_bluesky_credentials(self) -> bool:
        """Check if Bluesky credentials are configured."""
        return bool(
            self.bluesky_handle and
            self.bluesky_app_password
        )

    def validate_required_services(self):
        """Validate that at least basic services are configured."""
        # Validate LLM configuration
        if self.llm_provider == 'openai':
            if not self.openai_api_key:
                raise ValueError("OpenAI API key is required when llm_provider='openai'")
        elif self.llm_provider == 'ollama':
            print(f"INFO: Using Ollama with model '{self.ollama_model}' at {self.ollama_base_url}")
            print("INFO: Make sure Ollama is running: ollama serve")
        else:
            raise ValueError(f"Invalid llm_provider: {self.llm_provider}. Must be 'openai' or 'ollama'")

        if self.enable_twitter and not self.has_twitter_credentials:
            print("WARNING: Twitter enabled but credentials not configured. Disabling Twitter.")
            self.enable_twitter = False

        if self.enable_reddit and not self.has_reddit_credentials:
            print("WARNING: Reddit enabled but credentials not configured. Disabling Reddit.")
            self.enable_reddit = False

        if self.enable_bluesky and not self.has_bluesky_credentials:
            print("WARNING: Bluesky enabled but credentials not configured. Disabling Bluesky.")
            print("  To enable: create a free account at bsky.app, then generate an app password")
            print("  Add BLUESKY_HANDLE and BLUESKY_APP_PASSWORD to your .env file")
            self.enable_bluesky = False


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get or create global settings instance.

    Returns:
        Settings: Application settings
    """
    global _settings
    if _settings is None:
        # Look for .env file in project root
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        if os.path.exists(env_path):
            _settings = Settings(_env_file=env_path)
        else:
            _settings = Settings()

        # Validate configuration
        _settings.validate_required_services()

    return _settings


def reload_settings():
    """Reload settings from environment."""
    global _settings
    _settings = None
    return get_settings()


def get_llm():
    """
    Get configured LLM instance based on settings.

    Returns:
        LLM instance (either OpenAI or Ollama)
    """
    settings = get_settings()

    if settings.llm_provider == 'openai':
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.openai_model,
            temperature=settings.llm_temperature,
            api_key=settings.openai_api_key
        )
    elif settings.llm_provider == 'ollama':
        try:
            from langchain_community.llms import Ollama
            return Ollama(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
                temperature=settings.llm_temperature
            )
        except ImportError:
            raise ImportError(
                "langchain-community is required for Ollama. "
                "Install with: pip install langchain-community"
            )
    else:
        raise ValueError(f"Invalid llm_provider: {settings.llm_provider}")
