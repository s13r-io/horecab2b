# NAM Agentic Procurement Platform — MVP Prototype

AI-powered procurement assistant for restaurants. Demonstrates demand forecasting, vendor routing, and automated order dispatch through a WhatsApp-style chat interface.

## Quick Start

```bash
cd proto
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set ANTHROPIC_API_KEY in .env
python scripts/generate_pos_data.py
python db/init_db.py
uvicorn main:app --reload
```

Open http://localhost:8000 in your browser.

## Demo Scenarios

### Scenario 1: Emergency Stockout
Type in chat: **"We're out of chicken"**

The system will:
- Detect low stock intent via AG-INT (Claude API)
- Forecast daily chicken need using 7-day weighted average (AG-DPF)
- Route to best vendor by cost/reliability score (AG-MVR)
- Present a suggestion with vendor comparison and Approve button

Click **Approve** to dispatch formatted WhatsApp messages to vendors.

### Scenario 2: Pre-Dawn Forecast
Click **"Run Morning Forecast"** in the header.

The system forecasts all 20 ingredients, subtracts current inventory, routes each to the optimal vendor, and presents a full procurement plan with estimated costs.

### Scenario 3: Price Check
Type: **"What's the price of paneer?"**

Returns a vendor price comparison with reliability-adjusted scoring.

## Architecture

```
User (Chat UI) → FastAPI → Orchestrator
                              ├── AG-INT  (Intent Parser — Claude API)
                              ├── AG-DPF  (Demand Forecaster — weighted average)
                              ├── AG-MVR  (Vendor Router — cost/reliability scoring)
                              └── AG-DSP  (Dispatcher — message formatting)
```

- **Backend:** FastAPI + SQLite
- **Frontend:** Vanilla HTML/JS/CSS (no framework)
- **LLM:** Claude Sonnet for intent parsing only — no ML in forecasting

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat` | Main chat — routes through agent pipeline |
| POST | `/approve-order` | Approve a suggested order and dispatch |
| GET | `/forecast-today` | Run full daily demand forecast |
| GET | `/vendor-prices` | Price comparison for an ingredient |
| GET | `/health` | Health check |

## Railway Deployment

```bash
# Procfile uses: gunicorn main:app -w 1 -k uvicorn.workers.UvicornWorker
# Set ANTHROPIC_API_KEY as a Railway service variable
# PORT is auto-injected by Railway
```

SQLite is ephemeral on Railway — `init_database()` rebuilds schema on every startup.

## Key Design Decisions

- **No ML:** 7-day weighted average with event/weekend multipliers
- **No real HTTP dispatch:** AG-DSP formats messages only, never sends
- **No auth:** Railway URL is randomly generated, not publicly discoverable
- **Single worker (`-w 1`):** Required for SQLite concurrency safety
- **chicken_breast = 2kg inventory:** Intentionally low to trigger stockout demo
