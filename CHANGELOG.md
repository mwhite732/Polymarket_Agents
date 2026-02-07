# Changelog

## [Unreleased] – 2025-02-07

### Bug fixes & stability

- **429 rate limit crash** – Polymarket API 429 responses no longer cause infinite recursion / stack overflow. Retries are now a single loop with exponential backoff (max 5 attempts). Urllib3 retries no longer handle 429, so there’s one consistent retry path.
- **Data loss on social post save** – When one social post failed to store, `session.rollback()` was wiping all posts from that batch. Storage now commits after each successful post so a single failure doesn’t discard the rest.
- **RSS deduplication** – RSS post IDs used Python’s `hash()`, which changes between runs. Same articles were re-inserted every cycle. Switched to a stable SHA-256 hash of the article URL so duplicates are correctly skipped.
- **Duplicate gaps in DB** – Every cycle inserted new `detected_gaps` rows even when the same contract+gap_type was already detected, filling the DB with duplicates. New gaps are only stored if the same (contract_id, gap_type) wasn’t already detected within `GAP_DEDUPE_HOURS` (default 24h). Reporter now shows “latest per (contract, type)” so duplicate rows don’t clutter the report.

### Behavior & coverage

- **Hardcoded 10-contract limit removed** – Social/news data was only fetched for the first 10 contracts, so most of the 474 contracts never got sentiment or gap analysis. This is now configurable via `MAX_CONTRACTS_FOR_SOCIAL` (default 50). More contracts get social data and can be analyzed for gaps.
- **Sentiment only where there’s data** – Sentiment analysis runs only for contracts that have at least one related social post. Gap detection runs only for contracts that have at least one sentiment analysis. This avoids wasted work and focuses analysis where data exists.

### Configuration

- **`MAX_CONTRACTS_FOR_SOCIAL`** (default: 50) – Max contracts to fetch social/news data for per cycle.
- **`GAP_DEDUPE_HOURS`** (default: 24) – Skip storing a gap if the same contract+type was already detected within this many hours.
- **`GAP_SENTIMENT_PROB_SCALE`** (default: 0.4) – Scale from sentiment (-1..1) to implied probability: `0.5 + sentiment * scale`. Tunable if you want more/less sensitivity.

### Files touched

- `src/agents/data_collector.py` – Social limit, RSS stable ID, per-post commit.
- `src/services/polymarket_api.py` – 429 handled in loop, no recursion.
- `src/agents/gap_detector.py` – Gap dedupe before insert, only contracts with sentiment, configurable sentiment scale.
- `src/agents/sentiment_analyzer.py` – Only contracts with social posts.
- `src/agents/reporter.py` – Latest gap per (contract, type) for display.
- `src/config.py` – New settings.
- `config/.env.example` – New env vars and comments.

---

*Format loosely follows [Keep a Changelog](https://keepachangelog.com/).*
