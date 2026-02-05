# Quick Start Guide

Get up and running in 5 minutes - **100% FREE!**

## 🆓 Using Free Local LLMs (Recommended)

This guide uses **Ollama** for zero API costs.

**Want OpenAI instead?** See [Option 2](#option-2-using-openai-paid) below.

## Prerequisites Check

- [ ] Python 3.9+ installed
- [ ] PostgreSQL 12+ installed
- [ ] Ollama installed (instructions below)

## Installation (4 steps)

### 1. Install Ollama (FREE LLM)

**Windows:**
```bash
winget install Ollama.Ollama
# Or download from https://ollama.ai
```

**Mac:**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

Then start Ollama and pull a model:
```bash
# Start Ollama (keep running)
ollama serve

# In a new terminal, pull Llama 3.1
ollama pull llama3.1:8b
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Setup Database
```bash
createdb polymarket_gaps
psql -d polymarket_gaps -f migrations/init_db.sql
```

### 4. Configure
```bash
cp config/.env.example .env
```

Edit `.env` and set:
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/polymarket_gaps
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.1:8b
```

**That's it! No API key needed!**

## Run It!

```bash
# Test everything works
python run.py test

# Run demo (one cycle)
python run.py demo

# Run continuously
python run.py
```

## Common Commands

```bash
# Start system
python run.py                    # Continuous mode
python -m src.main continuous    # Alternative syntax

# Test modes
python run.py demo              # Demo with one cycle
python run.py once              # Run once and exit
python run.py test              # Test configuration

# Database operations
psql -d polymarket_gaps                          # Connect to DB
python -c "from src.database import get_db_manager; print(get_db_manager().get_stats())"  # Stats

# View logs
tail -f logs/app.log            # Linux/Mac
Get-Content logs/app.log -Wait  # Windows PowerShell
```

---

## Option 2: Using OpenAI (PAID)

If you prefer to use OpenAI GPT-4 instead of Ollama:

### Installation (3 steps)

1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

2. **Setup Database**
```bash
createdb polymarket_gaps
psql -d polymarket_gaps -f migrations/init_db.sql
```

3. **Configure**
```bash
cp config/.env.example .env
```

Edit `.env`:
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/polymarket_gaps
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-key-here
```

Then run: `python run.py demo`

**Cost:** ~$0.10-0.30 per cycle (~$15-45/month continuous)

---

## Troubleshooting

### Ollama: "Connection refused"
```bash
# Make sure Ollama is running
ollama serve

# Test it's working
curl http://localhost:11434
```

### Can't connect to database?
```bash
# Check PostgreSQL is running
pg_isready

# Test connection manually
psql -d polymarket_gaps
```

### Missing OpenAI key?
```bash
# Check .env file exists
cat .env | grep OPENAI_API_KEY

# Make sure it starts with sk-
```

### Module not found?
```bash
# Activate virtual environment
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Reinstall dependencies
pip install -r requirements.txt
```

## Configuration Quick Reference

**Ollama (FREE) - Minimum .env:**
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/polymarket_gaps
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.1:8b
```

**Ollama (FREE) - Recommended .env:**
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/polymarket_gaps
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.1:8b
TWITTER_BEARER_TOKEN=your-token  # Optional
REDDIT_CLIENT_ID=your-id          # Optional
REDDIT_CLIENT_SECRET=your-secret  # Optional
POLLING_INTERVAL=300
MIN_CONFIDENCE_SCORE=60
```

**OpenAI (PAID) - Minimum .env:**
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/polymarket_gaps
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
```

## Expected Output

When working correctly, you'll see:
```
[2026-02-05 10:30:45] POLYMARKET PRICING GAPS - Real-time Analysis
================================================================

RANK #1 - Confidence: 87/100
Contract: "Will Bitcoin reach $100k in 2026?" (Current: Yes 45% / No 55%)
Gap Type: Sentiment-Probability Mismatch
...
```

## Next Steps

1. ✅ Get it running with `python run.py demo`
2. 📊 Review output and verify gaps make sense
3. 🔧 Adjust settings in `.env` as needed
4. 🚀 Run continuously: `python run.py`
5. 📈 Build web dashboard (see DEVELOPMENT.md)

## Need Help?

- **Full setup:** See [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **Extension guide:** See [DEVELOPMENT.md](DEVELOPMENT.md)
- **Project overview:** See [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)
- **Example output:** See [EXAMPLE_OUTPUT.txt](EXAMPLE_OUTPUT.txt)

That's it! You're ready to detect pricing gaps. 🎯
