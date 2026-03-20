# CLAUDE.md — NAM Agentic Procurement Platform MVP

**Design doc (source of truth):** `docs/PROTOTYPE_DESIGN.md`
**All code lives under:** `proto/` (not yet created)

## Run

```bash
cd proto && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
python scripts/generate_pos_data.py && python db/init_db.py
uvicorn main:app --reload
```
Requires: `ANTHROPIC_API_KEY` in `.env`. Railway injects `PORT` automatically.

## Vendor Category Constraints (never violate — silently breaks routing)

- V001 Fresh Metro → vegetables only (tomato, onion, ginger_garlic, coriander_leaves, green_chili)
- V002 Hyperpure → mixed (vegetables, dairy, dry goods, meat)
- V003 Local Meat Supplier → chicken_breast only
- V004 Dairy Delight → paneer, butter, cream, yogurt only
- V005 Udaan → dry goods + spices only

**chicken_breast inventory = 2kg intentionally** (triggers stockout demo — never "fix" this)

## Guardrails (NEVER do)

1. No ML — weighted average only in AG-DPF
2. No WebSocket — simple POST/response (SSE is optional stretch)
3. No auth — CORS allows all origins (Railway URL is not public)
4. No real HTTP in AG-DSP — format messages only, never send
5. No frontend framework — vanilla HTML/JS/CSS only
6. No multi-language, no multi-restaurant, no admin panel
7. Procfile must use `-w 1` (single worker for SQLite safety)
8. `init_database()` always runs on startup — Railway SQLite is ephemeral
