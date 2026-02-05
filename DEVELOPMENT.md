# Development Guide - Extending to Web Dashboard

This guide explains how to extend the CLI system to include a web dashboard.

## Current Architecture

The system is built with extensibility in mind:

```
┌─────────────────────────────────────────┐
│         Multi-Agent System              │
│  ┌──────────────────────────────────┐  │
│  │   Data Collection Agent          │  │
│  └──────────────────────────────────┘  │
│  ┌──────────────────────────────────┐  │
│  │   Sentiment Analysis Agent       │  │
│  └──────────────────────────────────┘  │
│  ┌──────────────────────────────────┐  │
│  │   Gap Detection Agent            │  │
│  └──────────────────────────────────┘  │
│  ┌──────────────────────────────────┐  │
│  │   Reporting Agent                │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
           │
           ▼
    ┌──────────────┐
    │  PostgreSQL  │
    │   Database   │
    └──────────────┘
```

## Adding Web Dashboard

### Architecture Overview

```
┌─────────────────────────────────────────┐
│         Multi-Agent System              │
│         (Background Process)            │
└─────────────────────────────────────────┘
           │
           ▼
    ┌──────────────┐
    │  PostgreSQL  │ ←──── API Server (FastAPI)
    │   Database   │               │
    └──────────────┘               │
                                   ▼
                          ┌─────────────────┐
                          │  Web Dashboard  │
                          │   (React/Vue)   │
                          └─────────────────┘
```

### Step 1: Create API Layer

Create `src/api/` directory:

```python
# src/api/__init__.py
from .server import create_app

# src/api/server.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from .routes import contracts, gaps, sentiment, websocket

def create_app() -> FastAPI:
    app = FastAPI(
        title="Polymarket Gap Detector API",
        version="1.0.0"
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],  # React dev server
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(contracts.router, prefix="/api/contracts", tags=["contracts"])
    app.include_router(gaps.router, prefix="/api/gaps", tags=["gaps"])
    app.include_router(sentiment.router, prefix="/api/sentiment", tags=["sentiment"])
    app.include_router(websocket.router, prefix="/ws", tags=["websocket"])

    return app

# src/api/routes/gaps.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from ...database import get_db_manager
from ...database.models import DetectedGap, Contract

router = APIRouter()

def get_db():
    db = get_db_manager()
    with db.get_session() as session:
        yield session

@router.get("/", response_model=List[dict])
def get_gaps(
    limit: int = 50,
    min_confidence: int = 60,
    db: Session = Depends(get_db)
):
    """Get recent detected gaps."""
    gaps = db.query(DetectedGap).join(Contract).filter(
        DetectedGap.confidence_score >= min_confidence,
        DetectedGap.resolved == False
    ).order_by(DetectedGap.confidence_score.desc()).limit(limit).all()

    return [gap.to_dict() for gap in gaps]

@router.get("/{gap_id}")
def get_gap(gap_id: str, db: Session = Depends(get_db)):
    """Get specific gap details."""
    gap = db.query(DetectedGap).filter(DetectedGap.id == gap_id).first()
    if not gap:
        raise HTTPException(status_code=404, detail="Gap not found")
    return gap.to_dict()
```

### Step 2: Add WebSocket for Real-time Updates

```python
# src/api/routes/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import json
import asyncio

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@router.websocket("/gaps")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# In your main detection loop, broadcast new gaps:
# await manager.broadcast({"type": "new_gap", "data": gap_data})
```

### Step 3: Create Frontend Dashboard

#### Technology Stack
- **React** or **Vue.js** for UI
- **TailwindCSS** for styling
- **Recharts** or **Chart.js** for visualizations
- **Socket.IO** or native WebSocket for real-time updates

#### Frontend Structure
```
frontend/
├── src/
│   ├── components/
│   │   ├── GapCard.jsx           # Display individual gap
│   │   ├── GapList.jsx           # List of gaps
│   │   ├── SentimentChart.jsx    # Sentiment visualization
│   │   ├── ContractDetails.jsx   # Contract info
│   │   └── Dashboard.jsx         # Main dashboard
│   ├── services/
│   │   ├── api.js                # API client
│   │   └── websocket.js          # WebSocket connection
│   ├── hooks/
│   │   └── useGaps.js            # Custom hook for gaps data
│   └── App.jsx
├── package.json
└── tailwind.config.js
```

#### Sample React Component

```jsx
// src/components/GapCard.jsx
import React from 'react';
import { ArrowUpIcon, ArrowDownIcon } from '@heroicons/react/24/solid';

export default function GapCard({ gap }) {
  const confidenceColor = gap.confidence_score >= 80 ? 'green' :
                          gap.confidence_score >= 70 ? 'yellow' : 'gray';

  return (
    <div className={`bg-white rounded-lg shadow-lg p-6 border-l-4 border-${confidenceColor}-500`}>
      <div className="flex justify-between items-start">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            {gap.question}
          </h3>

          <div className="flex items-center space-x-4 mb-4">
            <span className={`px-3 py-1 rounded-full text-sm font-medium bg-${confidenceColor}-100 text-${confidenceColor}-800`}>
              Confidence: {gap.confidence_score}/100
            </span>
            <span className="text-sm text-gray-600">
              {gap.gap_type.replace('_', ' ').toUpperCase()}
            </span>
          </div>

          <p className="text-gray-700 mb-4">{gap.explanation}</p>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-500">Market Odds</p>
              <p className="text-xl font-bold">{(gap.market_odds * 100).toFixed(1)}%</p>
            </div>
            {gap.implied_odds && (
              <div>
                <p className="text-sm text-gray-500">Implied Odds</p>
                <p className="text-xl font-bold">{(gap.implied_odds * 100).toFixed(1)}%</p>
              </div>
            )}
          </div>
        </div>

        <div className="text-right">
          {gap.edge_percentage > 0 && (
            <div className="text-2xl font-bold text-green-600">
              +{gap.edge_percentage.toFixed(1)}%
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// src/hooks/useGaps.js
import { useState, useEffect } from 'react';

export function useGaps() {
  const [gaps, setGaps] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch initial gaps
    fetch('http://localhost:8000/api/gaps')
      .then(res => res.json())
      .then(data => {
        setGaps(data);
        setLoading(false);
      });

    // WebSocket for real-time updates
    const ws = new WebSocket('ws://localhost:8000/ws/gaps');

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === 'new_gap') {
        setGaps(prev => [message.data, ...prev]);
      }
    };

    return () => ws.close();
  }, []);

  return { gaps, loading };
}
```

### Step 4: Modify Main System for API Mode

```python
# src/main.py additions

def run_with_api_server():
    """Run detection system alongside API server."""
    import uvicorn
    from multiprocessing import Process

    # Start API server in separate process
    def start_api():
        from src.api.server import create_app
        app = create_app()
        uvicorn.run(app, host="0.0.0.0", port=8000)

    api_process = Process(target=start_api)
    api_process.start()

    try:
        # Run detection loop
        detector = PolymarketGapDetector()
        detector.run_continuous()
    finally:
        api_process.terminate()
        api_process.join()
```

### Step 5: Data Visualization Features

#### Key Dashboard Views

1. **Live Gaps Feed**
   - Real-time stream of detected gaps
   - Filter by confidence, type, category
   - Sort by edge, recency

2. **Contract Explorer**
   - Search and browse all contracts
   - View historical odds charts
   - See sentiment trends

3. **Sentiment Analysis**
   - Aggregate sentiment by category
   - Topic trends over time
   - Platform comparison (Twitter vs Reddit)

4. **Performance Metrics**
   - Historical accuracy of gap predictions
   - Resolution tracking
   - ROI if acting on gaps

5. **Analytics**
   - Gap frequency by type
   - Confidence distribution
   - Market category insights

### Step 6: Deployment

#### Backend Deployment
```bash
# Use Docker for easy deployment
docker-compose.yml:
  services:
    postgres:
      image: postgres:14
      environment:
        POSTGRES_DB: polymarket_gaps
        POSTGRES_PASSWORD: ${DB_PASSWORD}
      volumes:
        - ./data:/var/lib/postgresql/data

    detector:
      build: .
      environment:
        - DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@postgres:5432/polymarket_gaps
      depends_on:
        - postgres

    api:
      build: .
      command: uvicorn src.api.server:app --host 0.0.0.0
      ports:
        - "8000:8000"
      depends_on:
        - postgres
```

#### Frontend Deployment
```bash
# Build and deploy to Vercel/Netlify
npm run build
# Deploy dist/ folder
```

## Advanced Features to Add

### 1. Alert System
```python
# src/alerts/telegram.py
def send_telegram_alert(gap):
    """Send high-confidence gaps to Telegram."""
    if gap['confidence_score'] >= 85:
        message = f"🚨 High Confidence Gap!\n{gap['question']}\nConfidence: {gap['confidence_score']}"
        # Send via Telegram Bot API
```

### 2. Backtesting Framework
```python
# src/backtest/engine.py
def backtest_gaps(start_date, end_date):
    """Evaluate historical gap prediction accuracy."""
    # Fetch resolved gaps from period
    # Calculate actual outcomes
    # Compute accuracy, ROI metrics
```

### 3. ML Enhancement
```python
# Replace LLM sentiment with fine-tuned model
from transformers import pipeline

sentiment_model = pipeline(
    "sentiment-analysis",
    model="ProsusAI/finbert"  # Financial sentiment model
)
```

### 4. Multi-Exchange Support
```python
# Add other prediction markets
from src.services.kalshi_api import KalshiAPI
from src.services.manifold_api import ManifoldAPI

# Cross-market arbitrage detection
```

## Testing Dashboard Integration

1. Start backend: `python -m src.main api`
2. Start frontend: `cd frontend && npm start`
3. Open browser: `http://localhost:3000`
4. Verify real-time updates work

## Security Considerations

- Add authentication (JWT tokens)
- Rate limiting on API endpoints
- Input validation
- HTTPS in production
- Environment variable management
- Database connection pooling

## Performance Optimization

- Add Redis caching layer
- Implement database indexes
- Use CDN for frontend assets
- Optimize SQL queries
- Add pagination to API endpoints

## Monitoring and Observability

- Add Prometheus metrics
- Set up Grafana dashboards
- Implement error tracking (Sentry)
- Log aggregation (ELK stack)
- Uptime monitoring

This provides a complete roadmap for extending the CLI system to a full-featured web dashboard!
