# Polymarket Pricing Gap Detection System - Project Summary

## Overview

A sophisticated multi-agent system that identifies pricing inefficiencies in Polymarket prediction markets by analyzing contract data and social media sentiment in real-time.

## What This System Does

1. **Continuously monitors** active Polymarket contracts (with automatic expired contract filtering)
2. **Collects social media and news data** from RSS feeds (Reuters, BBC, CNN, AP, Google News), Bluesky, and optionally Twitter/X and Reddit
3. **Analyzes sentiment** using LLM (Ollama for free, or OpenAI) with batched processing for speed
4. **Detects pricing gaps** across four categories including cross-market arbitrage against Kalshi and Manifold Markets
5. **Reports opportunities** in a clear, actionable console format

## Technical Architecture

### Framework: CrewAI
**Why CrewAI?**
- Purpose-built for multi-agent orchestration
- Native task delegation between agents
- Clean separation of concerns
- Easy integration with LLM providers

### LLM: Ollama (Free) or OpenAI (Paid)
**Two options:**
- **Ollama (Recommended)**: Free local LLMs like Qwen 2.5 7B, Llama 3.1 8B. Zero API cost, data stays local.
- **OpenAI GPT-4**: Premium quality, slightly better reasoning (~10%), costs ~$0.10-0.30 per cycle.

Switch between them by changing one line in `.env` (`LLM_PROVIDER=ollama` or `LLM_PROVIDER=openai`).

### Database: PostgreSQL
**Why PostgreSQL?**
- Robust relational database for structured data
- Excellent support for time-series data
- JSONB for flexible evidence storage
- Materialized views for performance

## Four Agent System

### 1. Data Collection Agent
**Role:** Gather comprehensive market and social data
**Responsibilities:**
- Fetch active Polymarket contracts via paginated API (with overfetch strategy for diversity)
- Collect RSS news articles from Reuters, BBC, CNN, AP, Google News
- Search Bluesky for relevant posts via AT Protocol API
- Optionally search Twitter/X and Reddit (when API keys configured)
- Filter out expired contracts automatically
- Store everything in PostgreSQL with timestamps
- Track historical odds changes

**Key Features:**
- Rate limiting and retry logic for all external APIs
- Ethical data collection (respects ToS)
- Smart keyword extraction from contract questions (proper nouns prioritized, extensive stop word filtering)
- Deduplication of social posts (by post_id, with per-post error handling)

### 2. Sentiment Analysis Agent
**Role:** Analyze social media sentiment using AI
**Responsibilities:**
- Perform LLM-based sentiment analysis on posts
- Generate sentiment scores (-1 to +1 scale)
- Classify as positive/negative/neutral
- Extract key topics and themes
- Aggregate sentiment per contract

**Key Features:**
- Batched LLM analysis: sends 5 posts per LLM call (5x fewer API calls)
- Handles both Ollama (string) and OpenAI (object) response formats
- JSON repair for LLM output (strips markdown fences, fixes trailing commas)
- Fallback to single-post analysis on batch parse failures
- Skips contracts with fewer than 3 posts (MIN_POSTS_FOR_ANALYSIS)
- Confidence scoring for each analysis
- Historical sentiment tracking

### 3. Gap Detection Agent
**Role:** Identify pricing inefficiencies
**Responsibilities:**
- Detect sentiment-probability mismatches
- Identify information asymmetry (news not priced in)
- Find historical pattern deviations
- Detect cross-market arbitrage vs Kalshi and Manifold Markets
- Calculate confidence scores (0-100)
- Generate clear explanations with LLM

**Four Gap Types (all implemented):**

1. **Sentiment-Probability Mismatch**
   - Market odds don't match social sentiment
   - Example: 80% positive sentiment, but only 45% YES odds
   - High confidence when gap > 15% with sufficient data

2. **Information Asymmetry**
   - Recent news/events not yet reflected in prices
   - Detects rapid sentiment shifts (last 3h vs older)
   - Identifies when odds haven't moved accordingly

3. **Historical Pattern Deviation**
   - Current odds deviate significantly from historical average
   - Uses statistical analysis (z-scores, standard deviation)
   - Flags unusual price movements

4. **Cross-Market Arbitrage**
   - Searches Kalshi and Manifold Markets for equivalent contracts
   - Uses LLM to confirm market matches (avoids false positives)
   - Compares probabilities and flags discrepancies above configurable threshold (default 10%)
   - Stores competitor platform, URL, probability, and match confidence in evidence JSONB

### 4. Reporting Agent
**Role:** Rank and format results for presentation
**Responsibilities:**
- Fetch recent gaps from database
- Rank by confidence + edge composite score
- Format for beautiful console output using Rich library
- Present evidence clearly
- Generate summary statistics

**Output Features:**
- Color-coded panels by confidence level
- Clear breakdown of odds, evidence, and reasoning
- Metadata (category, detection time)
- Summary statistics

## Project Structure

```
polymarket_agents/
├── src/
│   ├── agents/                    # Four agent implementations
│   │   ├── data_collector.py     # Agent 1: Data collection (RSS, Bluesky, Twitter, Reddit)
│   │   ├── sentiment_analyzer.py # Agent 2: Batched LLM sentiment analysis
│   │   ├── gap_detector.py       # Agent 3: Gap detection + cross-market arbitrage
│   │   └── reporter.py           # Agent 4: Reporting
│   ├── database/                  # Database layer
│   │   ├── models.py             # SQLAlchemy models
│   │   └── connection.py         # Connection management
│   ├── services/                  # External API integrations
│   │   ├── polymarket_api.py     # Polymarket CLOB + Gamma API (paginated)
│   │   ├── kalshi_api.py         # Kalshi prediction market API (free, no auth)
│   │   ├── manifold_api.py       # Manifold Markets API (free, no auth)
│   │   ├── rss_news_scraper.py   # Free RSS feeds (Reuters, BBC, CNN, AP, Google News)
│   │   ├── bluesky_scraper.py    # Bluesky AT Protocol API (free account)
│   │   ├── twitter_scraper.py    # Twitter/X integration (optional, paid API)
│   │   └── reddit_scraper.py     # Reddit integration (optional)
│   ├── utils/                     # Utilities
│   │   └── logger.py             # Logging setup
│   ├── config.py                 # Pydantic settings management
│   └── main.py                   # Main orchestration
├── migrations/
│   └── init_db.sql               # Database schema
├── config/
│   └── .env.example              # Configuration template
├── requirements.txt              # Python dependencies
├── run.py                        # Quick start script
├── README.md                     # Main documentation
├── SETUP_GUIDE.md               # Detailed setup instructions
├── DEVELOPMENT.md               # Web dashboard extension guide
├── EXAMPLE_OUTPUT.txt           # Sample system output
└── PROJECT_SUMMARY.md           # This file
```

## Database Schema

### Key Tables

1. **contracts** - Polymarket contract data
2. **historical_odds** - Odds changes over time
3. **social_posts** - RSS articles, Bluesky posts, Twitter/Reddit posts
4. **sentiment_analysis** - LLM sentiment results
5. **detected_gaps** - Identified pricing gaps
6. **system_logs** - Application logs

### Materialized View
- **contract_sentiment_summary** - Pre-aggregated sentiment data for performance

## Key Features

### Ethical Data Collection
- Respects all API terms of service
- Implements proper rate limiting
- Uses official APIs when available
- Identifies with appropriate user agents
- No unauthorized scraping

### Real-time Operation
- Continuous monitoring with configurable intervals (default: 5 minutes)
- Async operations where beneficial
- Automatic retry with exponential backoff
- Graceful error handling

### Extensibility
- Modular architecture for easy enhancement
- Database-driven design for web dashboard integration
- Configuration via environment variables
- Plugin-ready structure for new agents

### Production-Ready Features
- Comprehensive logging (file + console)
- Database connection pooling
- Error tracking and recovery
- Resource cleanup on shutdown
- Configuration validation

## Usage Modes

### 1. Demo Mode
```bash
python run.py demo
```
- Runs one complete cycle
- Shows detailed output
- Perfect for testing

### 2. Single Cycle
```bash
python run.py once
```
- Runs once and exits
- Good for cron jobs

### 3. Continuous Monitoring
```bash
python run.py
```
- Runs indefinitely
- Production mode
- Automatic polling

### 4. Test Configuration
```bash
python run.py test
```
- Validates setup
- Tests database connection
- Checks API credentials

## Configuration

All configuration via `.env` file:

**Required:**
- `DATABASE_URL` - PostgreSQL connection string
- `LLM_PROVIDER` - `ollama` (free) or `openai` (paid)

**LLM Settings:**
- `OLLAMA_MODEL` - Ollama model name (default: `llama3.1:8b`)
- `OPENAI_API_KEY` - Required only if `LLM_PROVIDER=openai`

**Optional data sources:**
- `BLUESKY_HANDLE` / `BLUESKY_APP_PASSWORD` - For Bluesky posts (free account)
- `TWITTER_BEARER_TOKEN` - For Twitter data (paid API)
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` - For Reddit data

**Cross-Market Arbitrage:**
- `ENABLE_KALSHI` - Enable Kalshi comparison (default: true, free, no auth)
- `ENABLE_MANIFOLD` - Enable Manifold comparison (default: true, free, no auth)
- `ARBITRAGE_MIN_EDGE` - Minimum price difference to flag (default: 0.10)

**System Settings:**
- `POLLING_INTERVAL` - Seconds between cycles (default: 300)
- `MAX_CONTRACTS_PER_CYCLE` - Contracts to analyze (default: 20)
- `MIN_CONFIDENCE_SCORE` - Minimum confidence to report (default: 60)

## Extending to Web Dashboard

The system is architected for easy extension. See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed guide.

**Suggested Stack:**
- **Backend:** FastAPI for REST API + WebSocket
- **Frontend:** React or Vue.js with TailwindCSS
- **Real-time:** WebSocket for live gap updates
- **Visualization:** Recharts or Chart.js
- **Deployment:** Docker + Docker Compose

**Key Features to Add:**
- Live gaps feed with filters
- Contract explorer with charts
- Sentiment trend visualization
- Performance metrics and backtesting
- Alert system (Telegram, email)

## Performance Characteristics

**Typical Cycle Time:** 60-90 seconds
- Data collection: 20-30s
- Sentiment analysis: 20-30s
- Gap detection: 10-15s
- Reporting: <5s

**Resource Usage:**
- CPU: Low (mostly I/O bound)
- Memory: ~200-500MB (plus LLM memory if using Ollama)
- Database: ~100MB per month of data
- API Costs: $0.00 with Ollama, ~$0.10-0.30 per cycle with OpenAI

## Security & Privacy

- No personal data collection
- API keys stored in `.env` (not committed)
- Database access restricted to localhost by default
- Rate limiting prevents abuse
- Audit logging of all operations

## Recent Enhancements (Completed)

- Free local LLM support via Ollama (Qwen 2.5, Llama 3.1, Mistral, Phi-3)
- RSS news feed integration (Reuters, BBC, CNN, AP, Google News)
- Bluesky social media integration via AT Protocol API
- Batched LLM sentiment analysis (5 posts per call, ~5x faster)
- Cross-market arbitrage detection against Kalshi and Manifold Markets
- Expired contract filtering across all agents
- Paginated Polymarket API fetching with overfetch strategy
- Smart keyword extraction with extensive stop word filtering
- Duplicate social post handling with per-post error recovery

## Future Enhancements

1. **Additional Data Sources**
   - Farcaster, Lens Protocol
   - On-chain data (transaction volumes)

2. **Advanced Analytics**
   - ML models for sentiment (reduce LLM costs)
   - Backtesting framework with historical data
   - Accuracy tracking and model improvements

3. **Automation**
   - Automated trade execution (with safeguards)
   - Portfolio optimization
   - Risk management system

4. **Scaling**
   - Redis caching layer
   - Horizontal scaling with message queues
   - Multi-region deployment

## Success Metrics

The system is working well when:
- ✓ Cycles complete without errors
- ✓ Gaps detected have reasonable confidence (60-90)
- ✓ Evidence supports gap reasoning
- ✓ Database grows with historical data
- ✓ Sentiment aggregations are meaningful
- ✓ Patterns emerge over multiple cycles

## Limitations & Disclaimers

**This is an MVP/Prototype:**
- Not financial advice
- Requires human judgment for trading decisions
- Historical accuracy unknown (needs backtesting)
- Dependent on API availability and costs
- Limited by social media data quality

**Ethical Use:**
- For research and educational purposes
- Use responsibly and within platform ToS
- Verify opportunities independently
- Consider market impact of actions

## Getting Started

1. Read [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed instructions
2. Set up PostgreSQL and create database
3. Configure `.env` with API keys
4. Install dependencies: `pip install -r requirements.txt`
5. Run migrations: `psql -d polymarket_gaps -f migrations/init_db.sql`
6. Test configuration: `python run.py test`
7. Run demo: `python run.py demo`

## Documentation Files

- **README.md** - Project overview and quick start
- **SETUP_GUIDE.md** - Step-by-step installation instructions
- **DEVELOPMENT.md** - Guide for extending to web dashboard
- **EXAMPLE_OUTPUT.txt** - Sample system output
- **PROJECT_SUMMARY.md** - This comprehensive overview

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Verify configuration with `python run.py test`
3. Review documentation files
4. Check database with `psql -d polymarket_gaps`

## License

MIT License - Free to use, modify, and distribute.

## Acknowledgments

Built with:
- CrewAI for multi-agent orchestration
- Ollama / OpenAI for natural language understanding
- PostgreSQL for robust data storage
- Rich library for beautiful console output
- Feedparser for RSS news collection
- Bluesky AT Protocol for social media data
- Kalshi and Manifold Markets APIs for cross-market arbitrage
- PRAW for Reddit API
- Tweepy for Twitter API

---

**Ready to detect pricing gaps? Start with `python run.py demo`!** 🚀
