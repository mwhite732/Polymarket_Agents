# Polymarket Pricing Gap Detection System

An intelligent multi-agent system that identifies pricing inefficiencies in Polymarket prediction markets by analyzing contract data and social media sentiment in real-time.

**Latest:** See [CHANGELOG.md](CHANGELOG.md) for the full v2.0 release notes — 5 new data sources, live dashboard, DeepSeek LLM, ensemble sentiment, smart contract selection, backtesting, and more.

## Architecture Overview

This system uses **CrewAI** as the agentic framework for coordinating four specialized agents:

1. **Data Collection Agent**: Fetches Polymarket contracts and social media data from 8 sources
2. **Sentiment Analysis Agent**: Analyzes social sentiment using ensemble methods (VADER + TextBlob + LLM)
3. **Gap Detection Agent**: Identifies pricing inefficiencies across four categories with dynamic confidence scoring
4. **Ranking & Reporting Agent**: Prioritizes and formats opportunities

### Data Sources (8 total)

| Source | Type | Cost | Description |
|--------|------|------|-------------|
| **Polymarket** | Market data | Free | Contract odds, volume, liquidity via Gamma API |
| **Bluesky** | Social | Free | Public posts via AT Protocol |
| **GDELT** | News | Free | Global news monitoring, 65+ languages |
| **RSS Feeds** | News | Free | Reuters, BBC, CNN, AP, Google News |
| **Polymarket Comments** | Social | Free | Comments on Polymarket markets |
| **X Mirror (Nitter)** | Social | Free | Public tweets via Nitter mirrors (fallback) |
| **Tavily** | Web search | Paid | Real-time web search API |
| **Grok/xAI** | Social | Paid | X/Twitter sentiment via xAI API |

All paid sources are optional — system degrades gracefully with missing API keys.

### LLM Options

| Provider | Cost | Speed | Quality | Config |
|----------|------|-------|---------|--------|
| **DeepSeek** (Recommended) | ~$0.50/cycle | Fast | Excellent | `LLM_PROVIDER=deepseek` |
| **Ollama** (Free) | $0 | Moderate | Good | `LLM_PROVIDER=ollama` |
| **OpenAI** | ~$0.30/cycle | Fast | Excellent | `LLM_PROVIDER=openai` |

The system uses `get_fast_llm()` (always Ollama) for cheap tasks like keyword extraction, and the primary LLM for complex sentiment/gap analysis.

### Smart Contract Selection

Instead of analyzing every contract equally, the system uses a filter-and-rank approach:

1. **Fetch** the full universe (500+ active contracts) from Polymarket
2. **Store all** in the database for historical odds tracking
3. **Filter out garbage**: dead markets, no-odds contracts, basically-resolved (97%+/3%-)
4. **Rank remaining** by composite score and process best-first:
   - Volume (30%) — actively traded markets
   - Volatility (25%) — recent price movement / breaking news
   - Uncertainty (20%) — mid-range odds with room for mispricing
   - Near-expiry (10%) — resolving soon, most actionable
   - Liquidity + spread (15%) — tradeable markets

### Dual Search Strategy

Each social source performs two searches per contract:
- **Keyword search** — extracted topic keywords for broad sentiment
- **Contract title search** — the actual Polymarket question to find people discussing the specific bet

GDELT and RSS use keyword-only since news articles cover topics, not bet titles.

## Features

- **Real-time Monitoring**: Continuous polling with configurable intervals and interactive mode
- **8-Source Data Pipeline**: Social media, news, web search, and market data aggregation
- **Ensemble Sentiment Analysis**: VADER + TextBlob + LLM weighted combination with rolling windows
- **Four Gap Types**:
  - Sentiment-Probability Mismatches
  - Information Asymmetry Detection
  - Cross-Market Arbitrage (Kalshi + Manifold Markets)
  - Historical Pattern Deviations
- **Dynamic Confidence Scoring**: Multi-factor scoring considering gap size, data volume, source diversity, contract features
- **Contract Feature Engineering**: Volatility, momentum, time-to-expiry, spread analysis
- **Backtesting Framework**: Win rate and edge analysis on resolved predictions
- **Live Dashboard**: FastAPI web interface with gap explorer, sentiment charts, cycle history, data source monitoring
- **CSV Export**: Download filtered gaps for external analysis
- **Cycle History Tracking**: Every pipeline run logged with performance metrics
- **PostgreSQL Storage**: Full historical data for trend analysis
- **Ethical Data Collection**: Rate limiting, robots.txt compliance, platform ToS adherence

## Prerequisites

**Required:**
- Python 3.9+
- PostgreSQL 12+

**LLM (choose one):**
- **DeepSeek** (Recommended) — Sign up at platform.deepseek.com
- **Ollama** (FREE) — [Install guide](OLLAMA_SETUP.md)
- **OpenAI** (Paid) — From platform.openai.com

**Optional data sources:**
- Bluesky account (free — create at bsky.app)
- Tavily API key (from tavily.com)
- Grok/xAI API key (from x.ai)
- FMP API key (from financialmodelingprep.com)

## Installation

1. **Clone the repository**
```bash
git clone https://github.com/mwhite732/Polymarket_Agents.git
cd Polymarket_Agents
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up PostgreSQL database**
```bash
createdb polymarket_gaps
psql -d polymarket_gaps -f migrations/init_db.sql
psql -d polymarket_gaps -f migrations/002_upgrade_schema.sql
psql -d polymarket_gaps -f migrations/003_cycle_runs.sql
```

4. **Configure environment variables**
```bash
cp config/.env.example .env
# Edit .env with your credentials
```

## Configuration

Edit the `.env` file:

```env
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/polymarket_gaps

# LLM Provider (deepseek, ollama, or openai)
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_MODEL=deepseek-chat

# Ollama fallback (used for cheap tasks regardless of primary LLM)
OLLAMA_MODEL=qwen2.5:7b

# Free data sources (no keys needed)
ENABLE_GDELT=true
ENABLE_X_MIRROR=true

# Optional paid data sources
TAVILY_API_KEY=your_key_here
ENABLE_TAVILY=true

# Bluesky (free — create account at bsky.app)
BLUESKY_HANDLE=yourhandle.bsky.social
BLUESKY_APP_PASSWORD=your-app-password

# System settings
POLLING_INTERVAL=300
MAX_CONTRACTS_PER_CYCLE=100
ENABLE_BACKTESTING=true
ENABLE_ENSEMBLE_SENTIMENT=true
```

## Usage

### Interactive Mode (Recommended)
```bash
python run.py
# Runs one cycle, prompts before next. Dashboard stays alive at http://localhost:8000
```

### Other Modes
```bash
python run.py continuous    # Non-stop monitoring
python run.py once          # Single cycle, then exit
python run.py demo          # Demo with verbose output
python run.py dashboard     # Dashboard only (no analysis)
```

### Dashboard

Access the live dashboard at `http://localhost:8000` after starting any mode. Features:
- **Gap Explorer** — filterable list with confidence badges
- **Top Contracts** — ranked by social buzz and gap activity
- **Sentiment vs Price** — per-contract chart overlay
- **Cycle History** — performance log with timing and cost estimates
- **Data Sources** — live status of all 8 sources
- **Alerts** — notification banner for newly detected gaps
- **CSV Export** — download gaps at `/api/gaps/export`

## Project Structure

```
polymarket_agents/
├── src/
│   ├── agents/                    # CrewAI agent implementations
│   │   ├── data_collector.py            # 8-source data collection + smart contract selection
│   │   ├── sentiment_analyzer.py        # Ensemble sentiment (VADER + TextBlob + LLM)
│   │   ├── gap_detector.py              # Gap detection + dynamic confidence scoring
│   │   └── reporter.py                  # Ranking and formatted output
│   ├── database/                  # SQLAlchemy models and connection
│   │   ├── models.py                    # Contract, SocialPost, DetectedGap, CycleRun, etc.
│   │   └── connection.py               # Database manager with session handling
│   ├── services/                  # External API integrations
│   │   ├── polymarket_api.py            # Polymarket CLOB + Gamma API + comments
│   │   ├── bluesky_scraper.py           # Bluesky AT Protocol
│   │   ├── rss_news_scraper.py          # Free RSS news feeds
│   │   ├── gdelt_api.py                 # GDELT global news (free)
│   │   ├── tavily_search.py             # Tavily web search (paid)
│   │   ├── grok_sentiment.py            # Grok/xAI X sentiment (paid)
│   │   ├── x_mirror_scraper.py          # Nitter/XCancel tweet scraper (free)
│   │   ├── fmp_api.py                   # Financial Modeling Prep (paid)
│   │   ├── kalshi_api.py                # Kalshi cross-market arbitrage
│   │   ├── manifold_api.py              # Manifold Markets cross-reference
│   │   ├── twitter_scraper.py           # Twitter/X API (optional)
│   │   └── reddit_scraper.py            # Reddit API (optional)
│   ├── analysis/                  # Analysis modules
│   │   └── backtester.py                # Backtesting framework
│   ├── features/                  # Feature engineering
│   │   └── contract_features.py         # Contract-level feature computation
│   ├── sentiment/                 # Sentiment analysis
│   │   └── ensemble_sentiment.py        # VADER + TextBlob ensemble
│   ├── scoring/                   # Confidence scoring
│   │   └── confidence_scorer.py         # Dynamic multi-factor scoring
│   ├── dashboard/                 # Web dashboard
│   │   ├── app.py                       # FastAPI backend (8 endpoints)
│   │   └── static/index.html            # Frontend (vanilla JS + Chart.js)
│   ├── utils/
│   │   └── logger.py
│   ├── config.py                  # Pydantic settings (40+ config fields)
│   └── main.py                    # Main orchestration + cycle tracking
├── migrations/
│   ├── init_db.sql                # Initial schema
│   ├── 002_upgrade_schema.sql     # v2.0 schema additions
│   └── 003_cycle_runs.sql         # Cycle history table
├── config/
│   └── .env.example
├── requirements.txt
├── run.py                         # Entry point with multiple run modes
├── CHANGELOG.md
└── README.md
```

## Database Schema

| Table | Purpose |
|-------|---------|
| `contracts` | Polymarket contract data with current odds, volume, liquidity, category |
| `social_posts` | Social media posts from all 8 sources |
| `sentiment_analysis` | Per-post sentiment scores (LLM + VADER + TextBlob + ensemble) |
| `detected_gaps` | Pricing gaps with confidence scores and contract features |
| `historical_odds` | Time-series odds data for trend/volatility analysis |
| `cycle_runs` | Pipeline execution history with performance metrics |
| `sentiment_snapshots` | Aggregated sentiment windows per contract |
| `backtest_results` | Backtesting performance metrics |
| `system_logs` | System events and errors |

## Development Roadmap

- [x] Free local LLM support via Ollama
- [x] RSS news feed integration (Reuters, BBC, CNN, AP, Google News)
- [x] Bluesky social media integration
- [x] Batched LLM sentiment analysis (5x faster)
- [x] Cross-market arbitrage detection (Kalshi + Manifold Markets)
- [x] Expired contract filtering
- [x] Paginated contract fetching
- [x] **DeepSeek LLM support** (v2.0)
- [x] **5 new data sources** — Tavily, GDELT, Grok/xAI, X Mirror, FMP (v2.0)
- [x] **Ensemble sentiment analysis** — VADER + TextBlob + LLM (v2.0)
- [x] **Smart contract selection** — garbage filter + multi-factor ranking (v2.0)
- [x] **Dual search strategy** — keyword + contract title search (v2.0)
- [x] **Contract feature engineering** — volatility, momentum, time-to-expiry (v2.0)
- [x] **Dynamic confidence scoring** — multi-factor with social source weighting (v2.0)
- [x] **Backtesting framework** — win rate and edge analysis (v2.0)
- [x] **FastAPI dashboard** — gap explorer, charts, cycle history, source monitoring (v2.0)
- [x] **CSV export** for external analysis (v2.0)
- [x] **Cycle history tracking** with cost estimation (v2.0)
- [x] **Fixed Polymarket API parser** — odds and categories now correctly extracted (v2.0)
- [ ] Add more social media sources (Farcaster, Lens)
- [ ] Implement ML model for sentiment (reduce LLM costs)
- [ ] Add alerting system (email/Telegram)
- [ ] Implement automated trade execution (with safeguards)
- [ ] Add Supabase cloud database support
- [ ] LangSmith tracing integration

## Ethical Considerations

- **Rate Limiting**: All API calls respect platform limits
- **robots.txt Compliance**: Web scraping follows robots.txt rules
- **Terms of Service**: Implementation adheres to all platform ToS
- **Data Privacy**: No personal data collection
- **Transparency**: All data sources are clearly attributed

## License

MIT License - See LICENSE file for details

## Disclaimer

This software is for educational and research purposes only. Not financial advice.
Use at your own risk. Always verify opportunities independently before making trades.
