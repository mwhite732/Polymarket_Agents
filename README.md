# Polymarket Pricing Gap Detection System

An intelligent multi-agent system that identifies pricing inefficiencies in Polymarket prediction markets by analyzing contract data and social media sentiment in real-time.

## 🆓 Run Completely FREE with Ollama!

**NEW**: You can now run this system with **zero API costs** using Ollama (local LLMs).

**Two Options:**
1. **Ollama (FREE)** - Uses models like Llama 3.1, Mistral, Phi-3 locally
2. **OpenAI (PAID)** - Uses GPT-4 API (~$15-45/month)

For free setup, see [OLLAMA_SETUP.md](OLLAMA_SETUP.md) 🚀

## Architecture Overview

This system uses **CrewAI** as the agentic framework for coordinating four specialized agents:

1. **Data Collection Agent**: Fetches Polymarket contracts and social media data
2. **Sentiment Analysis Agent**: Analyzes social sentiment using LLM
3. **Gap Detection Agent**: Identifies pricing inefficiencies across four categories
4. **Ranking & Reporting Agent**: Prioritizes and formats opportunities

### Why CrewAI?
- Purpose-built for multi-agent orchestration
- Native support for agent collaboration and task delegation
- Clean separation of concerns between agents
- Easy integration with LLM providers

### LLM Options

**Option 1: Ollama (Recommended for getting started)**
- ✅ 100% FREE - No API costs
- ✅ Privacy - Data stays on your machine
- ✅ Fast - No network latency
- ✅ Quality - Llama 3.1 and Qwen 2.5 perform excellently
- 📖 See [OLLAMA_SETUP.md](OLLAMA_SETUP.md)

**Option 2: OpenAI GPT-4 (Premium quality)**
- Superior reasoning for complex gap detection
- Slightly more nuanced explanations
- ~10% better accuracy
- Costs ~$0.10-0.30 per cycle

## Features

- **Real-time Monitoring**: Continuous polling of active Polymarket contracts with automatic expired contract filtering
- **Multi-source Sentiment**: Aggregates signals from RSS news feeds (Reuters, BBC, CNN, AP, Google News), Bluesky, and optionally Twitter/X and Reddit
- **Batched LLM Analysis**: Sends multiple posts per LLM call for significantly faster sentiment processing
- **Four Gap Types** (all implemented):
  - Sentiment-Probability Mismatches
  - Information Asymmetry Detection
  - Cross-Market Arbitrage (compares prices across Kalshi and Manifold Markets)
  - Historical Pattern Deviations
- **Cross-Market Arbitrage**: Searches Kalshi and Manifold Markets for equivalent contracts, uses LLM to confirm matches, and flags pricing discrepancies exceeding a configurable threshold
- **Confidence Scoring**: 0-100 scale for each identified gap
- **PostgreSQL Storage**: Historical data for trend analysis
- **Ethical Data Collection**: Respects rate limits and platform ToS

## Prerequisites

**Required:**
- Python 3.9+
- PostgreSQL 12+

**LLM (choose one):**
- **Ollama** (FREE) - [Install guide](OLLAMA_SETUP.md)
- **OpenAI API key** (PAID) - From platform.openai.com

**Optional (for better data):**
- Bluesky account (free - create at bsky.app, then generate an app password)
- Twitter API credentials
- Reddit API credentials

## Installation

1. **Clone the repository**
```bash
cd c:\Users\Matt\Documents\GitHub\Polymarket_Agents
```

2. **Create virtual environment**
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up PostgreSQL database**
```bash
# Create database
createdb polymarket_gaps

# Run migrations
psql -d polymarket_gaps -f migrations/init_db.sql
```

5. **Configure environment variables**
```bash
cp config/.env.example .env
# Edit .env with your API keys and database credentials
```

## Configuration

Edit the `.env` file with your credentials:

### Option 1: Using Ollama (FREE)

```env
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/polymarket_gaps

# LLM - Use FREE local Ollama
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.1:8b

# Bluesky (Free - create account at bsky.app)
BLUESKY_HANDLE=yourhandle.bsky.social    # Optional
BLUESKY_APP_PASSWORD=your-app-password   # Optional

# Social Media (Optional)
TWITTER_BEARER_TOKEN=your_twitter_token  # Optional
REDDIT_CLIENT_ID=your_reddit_client_id   # Optional
REDDIT_CLIENT_SECRET=your_reddit_secret  # Optional

# Cross-Market Arbitrage (enabled by default, no keys needed)
ENABLE_KALSHI=true
ENABLE_MANIFOLD=true
ARBITRAGE_MIN_EDGE=0.10  # 10% minimum price difference to flag
```

See [OLLAMA_SETUP.md](OLLAMA_SETUP.md) for Ollama installation.

### Option 2: Using OpenAI (PAID)

```env
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/polymarket_gaps

# LLM - Use OpenAI API
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here

# System Settings
POLLING_INTERVAL=300  # seconds
MAX_CONTRACTS_PER_CYCLE=20
```

## Usage

### Basic Run
```bash
python src/main.py
```

### Output Format
```
[2026-02-05 10:30:45] POLYMARKET PRICING GAPS - Real-time Analysis
================================================================

RANK #1 - Confidence: 87/100
Contract: "Will Bitcoin reach $100k in 2026?" (Current: Yes 45% / No 55%)
Gap Type: Sentiment-Probability Mismatch
Explanation: Social sentiment overwhelmingly bullish (82% positive) while
market odds only at 45%. Recent announcements from major institutions not
yet reflected in pricing.
Evidence:
  - Twitter: 127 bullish posts vs 23 bearish (last 6h)
  - Reddit: r/cryptocurrency highly optimistic (avg sentiment: 0.76)
  - Recent news: 3 major adoption announcements in last 24h
---

RANK #2 - Confidence: 73/100
[...]
```

## Project Structure

```
polymarket_agents/
├── src/
│   ├── agents/              # Agent implementations
│   │   ├── data_collector.py       # Fetches contracts + social media data
│   │   ├── sentiment_analyzer.py   # Batched LLM sentiment analysis
│   │   ├── gap_detector.py         # Gap detection + cross-market arbitrage
│   │   └── reporter.py             # Ranking and formatted output
│   ├── database/            # Database models and connection
│   │   ├── models.py
│   │   └── connection.py
│   ├── services/            # External API integrations
│   │   ├── polymarket_api.py       # Polymarket CLOB + Gamma API
│   │   ├── kalshi_api.py           # Kalshi prediction market API
│   │   ├── manifold_api.py         # Manifold Markets API
│   │   ├── rss_news_scraper.py     # Free RSS news feeds
│   │   ├── bluesky_scraper.py      # Bluesky AT Protocol API
│   │   ├── twitter_scraper.py      # Twitter/X API (optional)
│   │   └── reddit_scraper.py       # Reddit API (optional)
│   ├── utils/               # Utility functions
│   │   └── logger.py
│   ├── config.py            # Pydantic settings management
│   └── main.py              # Main orchestration
├── config/
│   └── .env.example
├── migrations/
│   └── init_db.sql
├── requirements.txt
└── README.md
```

## Database Schema

### contracts
- Stores Polymarket contract data with historical odds

### social_posts
- Archives social media posts with metadata

### detected_gaps
- Records identified pricing gaps with confidence scores

### system_logs
- Tracks system events and errors

## Extending to Web Dashboard

This system is designed for easy extension to a web interface:

1. **API Layer**: Add FastAPI/Flask endpoints to expose:
   - Real-time gap data
   - Historical analysis
   - Contract details

2. **Frontend**: Build React/Vue dashboard to:
   - Display live gaps
   - Visualize sentiment trends
   - Show historical accuracy

3. **WebSocket**: For real-time updates to dashboard

4. **Suggested Structure**:
```
├── backend/
│   ├── api/
│   │   └── routes.py
│   └── websocket/
│       └── handler.py
└── frontend/
    ├── src/
    └── components/
```

## Ethical Considerations

- **Rate Limiting**: All API calls respect platform limits
- **robots.txt Compliance**: Web scraping follows robots.txt rules
- **Terms of Service**: Implementation adheres to all platform ToS
- **Data Privacy**: No personal data collection
- **Transparency**: All data sources are clearly attributed

## Troubleshooting

### Database Connection Issues
```bash
# Check PostgreSQL is running
pg_isready

# Verify connection string
psql postgresql://user:password@localhost:5432/polymarket_gaps
```

### API Rate Limits
- System automatically backs off on rate limit errors
- Consider increasing POLLING_INTERVAL in .env

### Missing Social Media Data
- System works with limited social data
- Gaps will have lower confidence without social signals

## Development Roadmap

- [x] Free local LLM support via Ollama
- [x] RSS news feed integration (Reuters, BBC, CNN, AP, Google News)
- [x] Bluesky social media integration
- [x] Batched LLM sentiment analysis (5x faster)
- [x] Cross-market arbitrage detection (Kalshi + Manifold Markets)
- [x] Expired contract filtering
- [x] Paginated contract fetching with overfetch strategy
- [ ] Add more social media sources (Farcaster, Lens)
- [ ] Implement ML model for sentiment (reduce LLM costs)
- [ ] Add backtesting framework
- [ ] Build web dashboard
- [ ] Add alerting system (email/Telegram)
- [ ] Implement automated trade execution (with safeguards)

## License

MIT License - See LICENSE file for details

## Disclaimer

This software is for educational and research purposes only. Not financial advice.
Use at your own risk. Always verify opportunities independently before making trades.
