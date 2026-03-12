# Changelog

## [v2.0] – 2026-03-11

### Major: Multi-Source Data Pipeline & Dashboard

This release transforms the system from a basic 2-source pipeline (Bluesky + RSS) into a comprehensive 8-source data collection and analysis platform with a live dashboard, ensemble sentiment analysis, smart contract selection, and backtesting.

### New Data Sources (5 added)

- **Tavily Web Search** — Real-time web search API for news, blogs, forums. Requires `TAVILY_API_KEY`. Falls back gracefully if missing.
- **GDELT News API** — Free global news monitoring (65+ languages, thousands of articles/hour). No API key required. Provides pre-computed tone/sentiment scores.
- **Grok/xAI Sentiment** — X/Twitter sentiment via xAI API (OpenAI-compatible). Requires `GROK_API_KEY`. Disabled if missing.
- **X Mirror Scraper** — Free Nitter/XCancel scraper as fallback when Grok is unavailable. Scrapes public tweets via BeautifulSoup. Respects rate limits and robots.txt.
- **FMP Financial Data** — Financial Modeling Prep API for market data on financially-relevant contracts. Requires `FMP_API_KEY`.
- **Polymarket Comments** — Scrapes comments/activity from Polymarket's own Gamma API. Always available, no key needed.

### Dual Search Strategy (keyword + title)

All social sources (Bluesky, X Mirror, Tavily, Grok) now perform **two searches** per contract:
1. **Keyword search** — extracted topic keywords for broad sentiment (e.g., "Trump immigration")
2. **Contract title search** — the actual Polymarket question to find people discussing the specific bet

GDELT and RSS use keyword-only (news articles cover topics, not bet titles). Results are deduplicated by `post_id` within each source before storage.

### Smart Contract Selection

Replaced the old "grab first N contracts" approach with a filter-and-rank system:
- **Fetches full universe** (500+ contracts) and stores ALL in database for historical tracking
- **Filters out garbage**: dead markets (no volume + no liquidity), no-odds contracts, basically-resolved (97%+ or 3%- odds)
- **Ranks remaining contracts** by composite score: volume (30%), volatility (25%), uncertainty/mid-odds (20%), near-expiry (10%), liquidity (10%), spread (5%)
- Best contracts processed first for social media analysis — volatile/breaking-news contracts prioritized

### Fixed: Polymarket API Parser

- **Odds were always 0** — Parser looked for `outcomes[0].price` (dict format) but API returns `outcomePrices` as a separate array. Now reads `outcomePrices` first, falls back to dict format.
- **Categories were always "Unknown"** — API nests category inside `events` array, not top-level. Now extracts from `events[0].category` or `events[0].slug`.

### DeepSeek LLM Support

- Added `deepseek` as LLM provider option via `LLM_PROVIDER=deepseek`
- Uses OpenAI-compatible API at `https://api.deepseek.com/v1`
- Configurable model via `DEEPSEEK_MODEL` (default: `deepseek-chat`)
- `get_fast_llm()` always uses Ollama for cheap tasks regardless of primary provider
- Graceful fallback: missing DeepSeek key auto-falls back to Ollama

### Ensemble Sentiment Analysis

- New `EnsembleSentiment` class combining VADER + TextBlob + LLM scores
- Weighted ensemble: `llm_weight * llm_score + (1-llm_weight) * avg(vader, textblob)`
- Rolling sentiment windows (6h, 12h, 24h) per contract
- New DB columns: `vader_score`, `textblob_score`, `ensemble_score` on `SentimentAnalysis`

### Dynamic Confidence Scoring

- New `ConfidenceScorer` class replaces inline confidence calculation
- Factors: gap size, data volume, cross-source consistency, social source count, contract features
- Social data weighting: confidence down-weighted when `social_sources_count == 0`
- Gap type adjustments: arbitrage = price-only, pattern = partial social dependency

### Contract Feature Engineering

- New `ContractFeatureEngine` class computing per-contract features
- Features: `time_to_expiry_hours`, `volatility_24h`, `momentum`, `volume_momentum`, `spread`, `is_near_resolution`, `implied_volatility_proxy`
- Stored as JSONB in `contract_features` column on `DetectedGap`

### Backtesting Framework

- New `Backtester` class querying resolved gaps to compute win rate and average edge
- Configurable confidence threshold and gap type filters
- Threshold tuning: finds optimal cutoffs per gap type
- Results stored in `backtest_results` table
- Accessible via dashboard API at `/api/backtest`

### FastAPI Dashboard

- Full web dashboard at `http://localhost:8000` (start with `python run.py dashboard`)
- **Gap Explorer** — sortable/filterable gap list with confidence badges, gap type filters, market search
- **Top Contracts** — contracts ranked by social buzz + gap activity
- **Sentiment vs Price Chart** — per-contract sentiment overlay on price history (Recharts)
- **Cycle History** — log of every pipeline run with duration, counts, success/failure, estimated cost
- **Data Sources Panel** — live status of all 8 data sources with total posts, +N/hr activity, active/configured/disabled indicators, LLM provider badge
- **New Gaps Alert Banner** — polls for recently detected gaps and shows notification count
- **CSV Export** — download filtered gaps as CSV at `/api/gaps/export`
- Dark theme, responsive layout, auto-refreshing (30s sources, 60s alerts)

### Cycle History Tracking

- New `CycleRun` database model tracking every pipeline execution
- Records: cycle number, start/end time, duration, success, contracts/posts/sentiments/gaps counts, LLM provider, errors, metadata
- Migration: `migrations/003_cycle_runs.sql`
- API endpoint: `/api/cycles`

### Interactive Run Mode

- `python run.py` now defaults to interactive mode — runs one cycle, prompts before next
- Dashboard stays alive between cycles
- Modes: `interactive` (default), `continuous`, `once`, `demo`, `dashboard`, `monitor`, `test`

### Configuration Additions

New `.env` variables (all optional, system degrades gracefully):
- `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL` — DeepSeek LLM
- `TAVILY_API_KEY`, `ENABLE_TAVILY` — Tavily web search
- `GROK_API_KEY`, `ENABLE_GROK` — Grok/xAI
- `FMP_API_KEY`, `ENABLE_FMP` — Financial Modeling Prep
- `ENABLE_X_MIRROR`, `ENABLE_GDELT` — Free scrapers
- `ENABLE_ENSEMBLE_SENTIMENT` — VADER+TextBlob ensemble
- `ENABLE_BACKTESTING` — Run backtest after each cycle
- `SCRAPER_REQUEST_DELAY`, `SCRAPER_USER_AGENT`, `SCRAPER_RESPECT_ROBOTS` — Scraper behavior

### Database Schema Changes

- `migrations/002_upgrade_schema.sql` — New columns + tables
- `migrations/003_cycle_runs.sql` — Cycle history table
- New tables: `sentiment_snapshots`, `backtest_results`, `cycle_runs`
- New columns on `SentimentAnalysis`: `vader_score`, `textblob_score`, `ensemble_score`
- New columns on `DetectedGap`: `social_sources_count`, `contract_features`

### New Files (19 created)

| File | Purpose |
|------|---------|
| `src/services/tavily_search.py` | Tavily web search client |
| `src/services/gdelt_api.py` | GDELT global news API |
| `src/services/grok_sentiment.py` | Grok/xAI X sentiment |
| `src/services/x_mirror_scraper.py` | Nitter/XCancel tweet scraper |
| `src/services/fmp_api.py` | Financial Modeling Prep API |
| `src/sentiment/ensemble_sentiment.py` | VADER + TextBlob + LLM ensemble |
| `src/features/contract_features.py` | Contract feature engineering |
| `src/scoring/confidence_scorer.py` | Dynamic confidence scoring |
| `src/analysis/backtester.py` | Backtesting framework |
| `src/dashboard/app.py` | FastAPI dashboard backend |
| `src/dashboard/static/index.html` | Dashboard frontend (vanilla JS + Chart.js) |
| `migrations/002_upgrade_schema.sql` | Schema upgrade migration |
| `migrations/003_cycle_runs.sql` | Cycle runs table migration |
| `src/analysis/__init__.py` | Package init |
| `src/dashboard/__init__.py` | Package init |
| `src/features/__init__.py` | Package init |
| `src/scoring/__init__.py` | Package init |
| `src/sentiment/__init__.py` | Package init |

### Modified Files (12 updated)

| File | Changes |
|------|---------|
| `src/config.py` | DeepSeek support, 15+ new config fields, credential properties, `get_fast_llm()` |
| `src/database/models.py` | `CycleRun` model, `SentimentSnapshot`, `BacktestResult`, new columns |
| `src/database/__init__.py` | New model exports |
| `src/services/__init__.py` | 5 new service exports |
| `src/services/polymarket_api.py` | Fixed odds parser (`outcomePrices`), fixed category extraction, added Polymarket comments |
| `src/services/manifold_api.py` | Comment collection for cross-reference |
| `src/agents/data_collector.py` | 5 new source integrations, dual search (keyword+title), smart contract filter+rank |
| `src/agents/sentiment_analyzer.py` | Ensemble sentiment integration |
| `src/agents/gap_detector.py` | Dynamic confidence scorer, ensemble score usage |
| `src/main.py` | Cycle history tracking, backtesting step |
| `src/dashboard/app.py` | 8 API endpoints |
| `run.py` | Interactive mode, dashboard mode |
| `requirements.txt` | New dependencies |

---

## [v1.1] – 2025-02-07

### Bug fixes & stability

- **429 rate limit crash** – Polymarket API 429 responses no longer cause infinite recursion / stack overflow. Retries are now a single loop with exponential backoff (max 5 attempts). Urllib3 retries no longer handle 429, so there's one consistent retry path.
- **Data loss on social post save** – When one social post failed to store, `session.rollback()` was wiping all posts from that batch. Storage now commits after each successful post so a single failure doesn't discard the rest.
- **RSS deduplication** – RSS post IDs used Python's `hash()`, which changes between runs. Same articles were re-inserted every cycle. Switched to a stable SHA-256 hash of the article URL so duplicates are correctly skipped.
- **Duplicate gaps in DB** – Every cycle inserted new `detected_gaps` rows even when the same contract+gap_type was already detected, filling the DB with duplicates. New gaps are only stored if the same (contract_id, gap_type) wasn't already detected within `GAP_DEDUPE_HOURS` (default 24h). Reporter now shows "latest per (contract, type)" so duplicate rows don't clutter the report.

### Behavior & coverage

- **Hardcoded 10-contract limit removed** – Social/news data was only fetched for the first 10 contracts, so most of the 474 contracts never got sentiment or gap analysis. This is now configurable via `MAX_CONTRACTS_FOR_SOCIAL` (default 50). More contracts get social data and can be analyzed for gaps.
- **Sentiment only where there's data** – Sentiment analysis runs only for contracts that have at least one related social post. Gap detection runs only for contracts that have at least one sentiment analysis. This avoids wasted work and focuses analysis where data exists.

### Configuration

- **`MAX_CONTRACTS_FOR_SOCIAL`** (default: 50) – Max contracts to fetch social/news data for per cycle.
- **`GAP_DEDUPE_HOURS`** (default: 24) – Skip storing a gap if the same contract+type was already detected within this many hours.
- **`GAP_SENTIMENT_PROB_SCALE`** (default: 0.4) – Scale from sentiment (-1..1) to implied probability: `0.5 + sentiment * scale`. Tunable if you want more/less sensitivity.

---

*Format loosely follows [Keep a Changelog](https://keepachangelog.com/).*
