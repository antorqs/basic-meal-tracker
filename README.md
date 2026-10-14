# Simple Meal Tracker

A mobile-first personal and family calorie/protein tracker powered by FastAPI, SQLite, Tailwind CDN, and Alpine.js.

## Run with Docker

```bash
docker compose up --build
```

Open <http://localhost:8000>. The SQLite file is persisted in `./data/meal_tracker.db`.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is documented at <http://localhost:8000/docs>.

## Included flows

- Seeded two-user switcher, date navigation, calorie/protein targets, remaining progress, and grouped daily meal feed.
- Ingredient autocomplete with live weight-based nutrition calculation.
- Recipe quick-load and save-as-recipe workflow.
- Snapshot-based historical logging, deletion, and one-tap duplication to the other user.
- Persistent SQLite schema with foreign keys and Docker volume storage.

