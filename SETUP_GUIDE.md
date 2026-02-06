# Polymarket Gap Detector - Setup Guide

Complete step-by-step guide to get the system running.

## Prerequisites

### 1. System Requirements
- Python 3.9 or higher
- PostgreSQL 12 or higher
- 8GB RAM minimum (16GB recommended)
- Stable internet connection

### 2. API Keys / Accounts

#### LLM Provider (choose one)

**Option A: Ollama (FREE - Recommended)**
1. Install Ollama (see [OLLAMA_SETUP.md](OLLAMA_SETUP.md))
2. Pull a model: `ollama pull llama3.1:8b`
3. No API key needed

**Option B: OpenAI (PAID)**
1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key (starts with `sk-`)

#### Bluesky Account (Optional, Free)
1. Create a free account at [bsky.app](https://bsky.app)
2. Go to Settings > App Passwords
3. Generate an app password
4. Note down your handle (e.g., `yourname.bsky.social`) and app password

#### Cross-Market APIs (No Setup Needed)
Kalshi and Manifold Markets APIs are free and require no authentication. They are enabled by default.

#### Twitter API (Optional, Paid)
1. Apply for Twitter Developer Account: [Twitter Developer Portal](https://developer.twitter.com/)
2. Create a new App
3. Generate a Bearer Token

#### Reddit API (Optional)
1. Go to [Reddit Apps](https://www.reddit.com/prefs/apps)
2. Click "Create App" or "Create Another App"
3. Select "script"
4. Note down Client ID and Client Secret

## Installation Steps

### Step 1: Clone Repository
```bash
cd c:\Users\Matt\Documents\GitHub\Polymarket_Agents
```

### Step 2: Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

If you encounter issues, try installing in groups:
```bash
# Core dependencies
pip install crewai langchain-openai openai

# Database
pip install psycopg2-binary sqlalchemy

# Social media
pip install praw tweepy

# Utilities
pip install python-dotenv pydantic pydantic-settings rich loguru
```

### Step 4: Setup PostgreSQL Database

#### Install PostgreSQL
- **Windows**: Download from [PostgreSQL Downloads](https://www.postgresql.org/download/windows/)
- **Mac**: `brew install postgresql@14`
- **Linux**: `sudo apt-get install postgresql postgresql-contrib`

#### Create Database
```bash
# Start PostgreSQL service
# Windows: Services → PostgreSQL → Start
# Mac: brew services start postgresql
# Linux: sudo systemctl start postgresql

# Create database
createdb polymarket_gaps

# Or using psql:
psql -U postgres
CREATE DATABASE polymarket_gaps;
\q
```

#### Run Migrations
```bash
psql -U postgres -d polymarket_gaps -f migrations/init_db.sql
```

Expected output:
```
CREATE EXTENSION
CREATE TABLE
CREATE TABLE
...
NOTICE:  Database schema created successfully!
```

### Step 5: Configure Environment Variables

1. Copy the example environment file:
```bash
cp config/.env.example .env
```

2. Edit `.env` file with your credentials:
```env
# Database (update with your PostgreSQL credentials)
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/polymarket_gaps

# LLM Provider: "ollama" (free) or "openai" (paid)
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.1:8b
# OPENAI_API_KEY=sk-your-key  # Only needed if LLM_PROVIDER=openai

# Bluesky (Optional, free - create account at bsky.app)
# BLUESKY_HANDLE=yourname.bsky.social
# BLUESKY_APP_PASSWORD=your-app-password

# Twitter (Optional, paid API)
# TWITTER_BEARER_TOKEN=your-twitter-bearer-token-here

# Reddit (Optional)
# REDDIT_CLIENT_ID=your-reddit-client-id
# REDDIT_CLIENT_SECRET=your-reddit-client-secret

# Cross-Market Arbitrage (enabled by default, no API keys needed)
ENABLE_KALSHI=true
ENABLE_MANIFOLD=true
ARBITRAGE_MIN_EDGE=0.10

# System Settings (defaults are fine)
POLLING_INTERVAL=300
MAX_CONTRACTS_PER_CYCLE=20
MIN_CONFIDENCE_SCORE=60
```

### Step 6: Test Database Connection

```bash
python -c "from src.database import init_database; db = init_database(); print('✓ Database connected!' if db.test_connection() else '✗ Connection failed')"
```

Expected output:
```
✓ Database connected!
```

### Step 7: Verify Configuration

```bash
python -c "from src.config import get_settings; s = get_settings(); s.validate_required_services(); print('✓ Configuration valid!')"
```

## Running the System

### Demo Mode (Single Cycle)
Run one complete analysis cycle to test everything:
```bash
python -m src.main demo
```

Expected output:
```
[STEP 1/4] Data Collection
✓ Collected X contracts, Y social posts

[STEP 2/4] Sentiment Analysis
✓ Analyzed sentiment for X contracts

[STEP 3/4] Gap Detection
✓ Detected X pricing gaps

[STEP 4/4] Generating Report
[Formatted report displays]

✓ Demo completed successfully!
```

### Single Cycle
Run once and exit:
```bash
python -m src.main once
```

### Continuous Monitoring (Production)
Run continuously with automatic polling:
```bash
python -m src.main continuous
```

Or simply:
```bash
python -m src.main
```

Press `Ctrl+C` to stop gracefully.

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'crewai'"
**Solution**: Make sure virtual environment is activated and dependencies installed
```bash
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### Issue: "Could not connect to database"
**Solution**: Check PostgreSQL is running and credentials are correct
```bash
# Test PostgreSQL
psql -U postgres -d polymarket_gaps

# If connection refused, start PostgreSQL service
```

### Issue: "OpenAI API key is required"
**Solution**: Either set `LLM_PROVIDER=ollama` for free local LLM, or set `OPENAI_API_KEY` in `.env`

### Issue: "No pricing gaps detected"
**Possible causes**:
1. Not enough social media data yet (RSS feeds work out of the box, but Bluesky/Twitter/Reddit are optional)
2. MIN_CONFIDENCE_SCORE set too high
3. Not enough historical data yet

**Solutions**:
- Configure Bluesky credentials for more social data (free)
- Lower MIN_CONFIDENCE_SCORE in `.env` temporarily
- Run multiple cycles to build historical data

### Issue: Rate Limiting Errors
**Solution**: Increase POLLING_INTERVAL or reduce MAX_CONTRACTS_PER_CYCLE in `.env`
```env
POLLING_INTERVAL=600  # 10 minutes instead of 5
MAX_CONTRACTS_PER_CYCLE=10  # Fewer contracts per cycle
```

## Monitoring and Logs

Logs are stored in the `logs/` directory:
- `logs/app.log` - All INFO and above
- `logs/errors.log` - Only errors and critical issues

View logs in real-time:
```bash
# Windows
Get-Content logs/app.log -Wait -Tail 50

# Linux/Mac
tail -f logs/app.log
```

## Database Maintenance

### View Statistics
```bash
python -c "from src.database import get_db_manager; db = get_db_manager(); print(db.get_stats())"
```

### Refresh Materialized Views
```bash
python -c "from src.database import get_db_manager; db = get_db_manager(); db.refresh_materialized_view()"
```

### Archive Old Data
```bash
python -c "from src.database import get_db_manager; db = get_db_manager(); db.cleanup_old_data()"
```

## Performance Optimization

### For Limited Social Media Access
If you don't have Twitter/Reddit APIs:
```env
ENABLE_TWITTER=false
ENABLE_REDDIT=false
```
System will still work but with lower confidence scores.

### For Faster Cycles
```env
MAX_CONTRACTS_PER_CYCLE=5  # Analyze fewer contracts
SENTIMENT_BATCH_SIZE=25     # Smaller batches
```

### For Zero LLM Costs
```env
LLM_PROVIDER=ollama          # Use free local model
OLLAMA_MODEL=llama3.1:8b     # Or qwen2.5:7b, mistral, phi3
```

## Next Steps

1. **Run Demo Mode** to verify everything works
2. **Let it run for a few cycles** to build historical data
3. **Monitor the output** and adjust confidence thresholds
4. **Review the logs** for any warnings or errors
5. **Plan dashboard integration** using the database as backend

## Getting Help

- Check logs in `logs/` directory
- Review database data: `psql -U postgres -d polymarket_gaps`
- Verify configuration: `python -c "from src.config import get_settings; print(get_settings())"`

## Security Best Practices

1. **Never commit `.env` file** - it contains secrets
2. **Use strong PostgreSQL password**
3. **Restrict database access** to localhost only
4. **Rotate API keys regularly**
5. **Monitor API usage** to avoid unexpected costs

## Success Criteria

You'll know it's working when:
- ✓ Demo mode completes without errors
- ✓ Console displays formatted pricing gaps
- ✓ Database contains contracts and social posts
- ✓ Logs show successful completion
- ✓ Confidence scores are reasonable (50-90 range)

Congratulations! Your Polymarket Gap Detector is now operational. 🎉
