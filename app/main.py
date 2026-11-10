from contextlib import asynccontextmanager
from datetime import date as date_type, timedelta
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("MEAL_TRACKER_DB", str(ROOT / "meal_tracker.db")))


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, target_calories INTEGER NOT NULL DEFAULT 2000, target_protein INTEGER NOT NULL DEFAULT 140);
        CREATE TABLE IF NOT EXISTS user_targets (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, effective_date TEXT NOT NULL, target_calories INTEGER NOT NULL DEFAULT 0, target_protein INTEGER NOT NULL DEFAULT 0, target_carbs REAL NOT NULL DEFAULT 0, target_sugar REAL NOT NULL DEFAULT 0, target_fat REAL NOT NULL DEFAULT 0, UNIQUE(user_id, effective_date));
        CREATE TABLE IF NOT EXISTS ingredients (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, calories_per_100g REAL NOT NULL DEFAULT 0, protein_per_100g REAL NOT NULL DEFAULT 0, carbs_per_100g REAL NOT NULL DEFAULT 0, sugar_per_100g REAL NOT NULL DEFAULT 0, fat_per_100g REAL NOT NULL DEFAULT 0, counts_as_added_sugar INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS meals (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS meal_items (id INTEGER PRIMARY KEY, meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE, ingredient_id INTEGER NOT NULL REFERENCES ingredients(id), default_weight REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS daily_logs (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, date TEXT NOT NULL, meal_type TEXT NOT NULL, total_calories REAL NOT NULL DEFAULT 0, total_protein REAL NOT NULL DEFAULT 0, total_carbs REAL NOT NULL DEFAULT 0, total_sugar REAL NOT NULL DEFAULT 0, total_fat REAL NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS daily_log_items (id INTEGER PRIMARY KEY, daily_log_id INTEGER NOT NULL REFERENCES daily_logs(id) ON DELETE CASCADE, ingredient_name TEXT NOT NULL, weight REAL NOT NULL, calories REAL NOT NULL DEFAULT 0, protein REAL NOT NULL DEFAULT 0, carbs REAL NOT NULL DEFAULT 0, sugar REAL NOT NULL DEFAULT 0, fat REAL NOT NULL DEFAULT 0, counts_as_added_sugar INTEGER NOT NULL DEFAULT 0);
        """)
        migrations = {
            "users": {"show_extended_nutrients": "INTEGER NOT NULL DEFAULT 0"},
            "user_targets": {"target_carbs": "REAL NOT NULL DEFAULT 0", "target_sugar": "REAL NOT NULL DEFAULT 0", "target_fat": "REAL NOT NULL DEFAULT 0"},
            "ingredients": {"carbs_per_100g": "REAL NOT NULL DEFAULT 0", "sugar_per_100g": "REAL NOT NULL DEFAULT 0", "fat_per_100g": "REAL NOT NULL DEFAULT 0", "counts_as_added_sugar": "INTEGER NOT NULL DEFAULT 0"},
            "daily_logs": {"total_carbs": "REAL NOT NULL DEFAULT 0", "total_sugar": "REAL NOT NULL DEFAULT 0", "total_fat": "REAL NOT NULL DEFAULT 0"},
            "daily_log_items": {"carbs": "REAL NOT NULL DEFAULT 0", "sugar": "REAL NOT NULL DEFAULT 0", "fat": "REAL NOT NULL DEFAULT 0", "counts_as_added_sugar": "INTEGER NOT NULL DEFAULT 0"},
        }
        for table, columns in migrations.items():
            existing = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
            for column, definition in columns.items():
                if column not in existing:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            db.executemany("INSERT INTO users(name,target_calories,target_protein) VALUES (?,?,?)", [("Alex", 2200, 160), ("Sam", 1800, 120)])
        for user in db.execute("SELECT id,target_calories,target_protein FROM users").fetchall():
            db.execute("INSERT OR IGNORE INTO user_targets(user_id,effective_date,target_calories,target_protein,target_carbs,target_sugar,target_fat) VALUES (?,?,?,?,0,0,0)", (user["id"], "1900-01-01", user["target_calories"], user["target_protein"]))
        if db.execute("SELECT COUNT(*) FROM ingredients").fetchone()[0] == 0:
            db.executemany("INSERT INTO ingredients(name,calories_per_100g,protein_per_100g) VALUES (?,?,?)", [
                ("Chicken breast", 165, 31), ("Oats", 389, 16.9), ("Greek yogurt", 59, 10.3), ("Egg", 143, 12.6), ("Rice, cooked", 130, 2.7), ("Banana", 89, 1.1), ("Whey protein", 400, 80), ("Avocado", 160, 2),
            ])


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="Simple Meal Tracker", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


class IngredientIn(BaseModel):
    name: str = Field(min_length=1)
    calories_per_100g: float = Field(ge=0)
    protein_per_100g: float = Field(ge=0)
    carbs_per_100g: float = Field(default=0, ge=0)
    sugar_per_100g: float = Field(default=0, ge=0)
    fat_per_100g: float = Field(default=0, ge=0)
    counts_as_added_sugar: bool = False


class ItemIn(BaseModel):
    name: str = Field(min_length=1)
    weight: float = Field(gt=0)
    calories: float = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(default=0, ge=0)
    sugar: float = Field(default=0, ge=0)
    fat: float = Field(default=0, ge=0)
    calories_per_100g: float = Field(default=0, ge=0)
    protein_per_100g: float = Field(default=0, ge=0)
    carbs_per_100g: float = Field(default=0, ge=0)
    sugar_per_100g: float = Field(default=0, ge=0)
    fat_per_100g: float = Field(default=0, ge=0)
    counts_as_added_sugar: bool = False


class MealIn(BaseModel):
    name: str = Field(min_length=1)
    items: list[ItemIn]


class LogIn(BaseModel):
    user_id: int
    date: str
    meal_type: str
    items: list[ItemIn]


class RecalculateConfirm(BaseModel):
    fingerprint: str


class UserUpdate(BaseModel):
    name: str | None = None
    effective_date: str | None = None
    target_calories: int | None = Field(default=None, ge=0)
    target_protein: int | None = Field(default=None, ge=0)
    target_carbs: float | None = Field(default=None, ge=0)
    target_sugar: float | None = Field(default=None, ge=0)
    target_fat: float | None = Field(default=None, ge=0)
    show_extended_nutrients: bool | None = None


def rows(sql, args=()):
    with connect() as db:
        return [dict(r) for r in db.execute(sql, args).fetchall()]


@app.get("/")
def index():
    return FileResponse(ROOT / "static/index.html")


@app.get("/api/users")
def users():
    return rows("SELECT id,name,show_extended_nutrients FROM users ORDER BY id")


@app.put("/api/users/{user_id}")
def update_user(user_id: int, payload: UserUpdate):
    values = payload.model_dump()
    with connect() as db:
        if not db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone(): raise HTTPException(404, "User not found")
        db.execute("UPDATE users SET name=COALESCE(?,name) WHERE id=?", (values["name"], user_id))
        if values["show_extended_nutrients"] is not None:
            db.execute("UPDATE users SET show_extended_nutrients=? WHERE id=?", (int(values["show_extended_nutrients"]), user_id))
        target_fields = ("target_calories", "target_protein", "target_carbs", "target_sugar", "target_fat")
        if all(values[field] is not None for field in target_fields):
            effective = values["effective_date"] or str(date_type.today())
            db.execute("INSERT INTO user_targets(user_id,effective_date,target_calories,target_protein,target_carbs,target_sugar,target_fat) VALUES (?,?,?,?,?,?,?) ON CONFLICT(user_id,effective_date) DO UPDATE SET target_calories=excluded.target_calories,target_protein=excluded.target_protein,target_carbs=excluded.target_carbs,target_sugar=excluded.target_sugar,target_fat=excluded.target_fat", (user_id, effective, *(values[field] for field in target_fields)))
    return {"ok": True}


@app.get("/api/users/{user_id}/targets")
def target_history(user_id: int):
    return rows("SELECT * FROM user_targets WHERE user_id=? ORDER BY effective_date DESC", (user_id,))


@app.get("/api/ingredients")
def ingredients(q: str = Query("")):
    limit = " LIMIT 20" if q else ""
    return rows(f"SELECT * FROM ingredients WHERE name LIKE ? ORDER BY name{limit}", (f"%{q}%",))


@app.post("/api/ingredients")
def create_ingredient(payload: IngredientIn):
    try:
        with connect() as db:
            cur = db.execute("INSERT INTO ingredients(name,calories_per_100g,protein_per_100g,carbs_per_100g,sugar_per_100g,fat_per_100g,counts_as_added_sugar) VALUES (?,?,?,?,?,?,?)", (payload.name, payload.calories_per_100g, payload.protein_per_100g, payload.carbs_per_100g, payload.sugar_per_100g, payload.fat_per_100g, int(payload.counts_as_added_sugar)))
            return {"id": cur.lastrowid, **payload.model_dump()}
    except sqlite3.IntegrityError: raise HTTPException(409, "Ingredient already exists")


@app.put("/api/ingredients/{ingredient_id}")
def update_ingredient(ingredient_id: int, payload: IngredientIn):
    try:
        with connect() as db:
            if not db.execute("SELECT 1 FROM ingredients WHERE id=?", (ingredient_id,)).fetchone(): raise HTTPException(404, "Ingredient not found")
            db.execute("UPDATE ingredients SET name=?,calories_per_100g=?,protein_per_100g=?,carbs_per_100g=?,sugar_per_100g=?,fat_per_100g=?,counts_as_added_sugar=? WHERE id=?", (payload.name, payload.calories_per_100g, payload.protein_per_100g, payload.carbs_per_100g, payload.sugar_per_100g, payload.fat_per_100g, int(payload.counts_as_added_sugar), ingredient_id))
    except sqlite3.IntegrityError: raise HTTPException(409, "Ingredient name already exists")
    return {"id": ingredient_id, **payload.model_dump()}


@app.get("/api/meals")
def meals():
    output = []
    for meal in rows("SELECT * FROM meals ORDER BY name"):
        meal["items"] = rows("SELECT i.name, mi.default_weight AS weight FROM meal_items mi JOIN ingredients i ON i.id=mi.ingredient_id WHERE mi.meal_id=?", (meal["id"],))
        output.append(meal)
    return output


@app.post("/api/meals")
def create_meal(payload: MealIn):
    with connect() as db:
        cur = db.execute("INSERT INTO meals(name) VALUES (?)", (payload.name,)); meal_id = cur.lastrowid
        for item in payload.items:
            ing = db.execute("SELECT id FROM ingredients WHERE lower(trim(name))=lower(trim(?)) ORDER BY id LIMIT 1", (item.name,)).fetchone()
            if not ing: raise HTTPException(400, f"Unknown ingredient: {item.name}")
            db.execute("INSERT INTO meal_items(meal_id,ingredient_id,default_weight) VALUES (?,?,?)", (meal_id, ing["id"], item.weight))
    return {"id": meal_id, "name": payload.name}


def summary(user_id, day):
    user = rows("SELECT * FROM users WHERE id=?", (user_id,))
    if not user: raise HTTPException(404, "User not found")
    logs = rows("SELECT * FROM daily_logs WHERE user_id=? AND date=? ORDER BY id", (user_id, day))
    for log in logs: log["items"] = rows("SELECT * FROM daily_log_items WHERE daily_log_id=? ORDER BY id", (log["id"],))
    consumed = {key: sum(x[f"total_{key}"] for x in logs) for key in ("calories", "protein", "carbs", "sugar", "fat")}
    added_sugar = sum(item["sugar"] for log in logs for item in log["items"] if item["counts_as_added_sugar"])
    u = user[0]
    target = rows("SELECT target_calories,target_protein,target_carbs,target_sugar,target_fat,effective_date FROM user_targets WHERE user_id=? AND effective_date<=? ORDER BY effective_date DESC LIMIT 1", (user_id, day))
    active = target[0] if target else {"target_calories": 2000, "target_protein": 140, "target_carbs": 0, "target_sugar": 0, "target_fat": 0, "effective_date": None}
    u.update(active)
    targets = {key: active[f"target_{key}"] for key in consumed}
    remaining = {key: max(0, targets[key] - consumed[key]) for key in consumed}
    remaining["sugar"] = max(0, targets["sugar"] - added_sugar)
    consumed["added_sugar"] = added_sugar
    return {"user": u, "date": day, "consumed": consumed, "targets": targets, "remaining": remaining, "logs": logs}


@app.get("/api/summary")
def get_summary(user_id: int = 1, date: str | None = None):
    return summary(user_id, date or str(date_type.today()))


REPORT_METRICS = ("calories", "protein", "carbs", "fat", "added_sugar")
REPORT_TARGET_COLUMNS = {
    "calories": "target_calories",
    "protein": "target_protein",
    "carbs": "target_carbs",
    "fat": "target_fat",
    "added_sugar": "target_sugar",
}
REPORT_DEFAULT_TARGETS = {
    "target_calories": 2000,
    "target_protein": 140,
    "target_carbs": 0,
    "target_sugar": 0,
    "target_fat": 0,
}


def parse_report_date(value, field_name):
    try:
        parsed = date_type.fromisoformat(value)
    except (TypeError, ValueError):
        raise HTTPException(400, f"{field_name} must be a valid YYYY-MM-DD date")
    if parsed.isoformat() != value:
        raise HTTPException(400, f"{field_name} must be a valid YYYY-MM-DD date")
    return parsed


def report_user(user_id):
    user = rows("SELECT id,name FROM users WHERE id=?", (user_id,))
    if not user:
        raise HTTPException(404, "User not found")
    return user[0]


def report_days(user_id, start, end):
    dates = []
    current = start
    while current <= end:
        dates.append(current.isoformat())
        current += timedelta(days=1)

    daily = {
        day: {
            "date": day,
            "has_logs": False,
            "values": {metric: 0.0 for metric in REPORT_METRICS},
            "goals": {},
            "progress_percent": {},
            "leaders": {},
        }
        for day in dates
    }
    logs = rows(
        "SELECT id,date,meal_type,total_calories,total_protein,total_carbs,total_fat "
        "FROM daily_logs WHERE user_id=? AND date>=? AND date<=? ORDER BY date,id",
        (user_id, dates[0], dates[-1]),
    ) if dates else []
    for log in logs:
        item = daily[log["date"]]
        item["has_logs"] = True
        for metric in ("calories", "protein", "carbs", "fat"):
            item["values"][metric] += log[f"total_{metric}"]

    leaders_by_day = {day: {} for day in dates}
    if logs:
        item_rows = rows(
            "SELECT dl.date,dl.meal_type,dli.ingredient_name,dli.weight,dli.calories,"
            "dli.protein,dli.carbs,dli.fat,dli.sugar,dli.counts_as_added_sugar "
            "FROM daily_log_items dli JOIN daily_logs dl ON dl.id=dli.daily_log_id "
            "WHERE dl.user_id=? AND dl.date>=? AND dl.date<=? ORDER BY dl.date,dl.id,dli.id",
            (user_id, dates[0], dates[-1]),
        )
        for row in item_rows:
            item = daily[row["date"]]
            if row["counts_as_added_sugar"]:
                item["values"]["added_sugar"] += row["sugar"]
            name_key = row["ingredient_name"].strip().casefold()
            ingredient = leaders_by_day[row["date"]].setdefault(
                name_key,
                {
                    "ingredient": row["ingredient_name"],
                    "grams": 0.0,
                    "values": {metric: 0.0 for metric in REPORT_METRICS},
                    "meals": set(),
                },
            )
            ingredient["grams"] += row["weight"]
            ingredient["meals"].add(row["meal_type"])
            for metric in ("calories", "protein", "carbs", "fat"):
                ingredient["values"][metric] += row[metric]
            if row["counts_as_added_sugar"]:
                ingredient["values"]["added_sugar"] += row["sugar"]

    targets = rows(
        "SELECT effective_date,target_calories,target_protein,target_carbs,target_sugar,target_fat "
        "FROM user_targets WHERE user_id=? AND effective_date<=? ORDER BY effective_date",
        (user_id, dates[-1]),
    ) if dates else []
    active_target = REPORT_DEFAULT_TARGETS.copy()
    target_index = 0
    for day in dates:
        while target_index < len(targets) and targets[target_index]["effective_date"] <= day:
            active_target = targets[target_index]
            target_index += 1
        item = daily[day]
        item["goals"] = {
            metric: active_target[REPORT_TARGET_COLUMNS[metric]] for metric in REPORT_METRICS
        }
        item["progress_percent"] = {
            metric: (item["values"][metric] / item["goals"][metric] * 100)
            if item["goals"][metric] > 0 else None
            for metric in REPORT_METRICS
        }
        day_ingredients = leaders_by_day[day]
        for metric in REPORT_METRICS:
            maximum = max((entry["values"][metric] for entry in day_ingredients.values()), default=0)
            if maximum <= 0:
                item["leaders"][metric] = []
                continue
            item["leaders"][metric] = [
                {
                    "ingredient": entry["ingredient"],
                    "grams": entry["grams"],
                    "value": entry["values"][metric],
                    "meals": sorted(entry["meals"]),
                }
                for entry in day_ingredients.values()
                if abs(entry["values"][metric] - maximum) <= max(1e-9, abs(maximum) * 1e-9)
            ]
    return daily


def report_window(start, end, daily):
    dates = []
    current = start
    while current <= end:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    included = [daily[day] for day in dates if daily[day]["has_logs"]]
    count = len(included)
    averages = {
        "logged_days": count,
        "values": {
            metric: sum(item["values"][metric] for item in included) / count if count else None
            for metric in REPORT_METRICS
        },
        "goals": {
            metric: sum(item["goals"][metric] for item in included) / count if count else None
            for metric in REPORT_METRICS
        },
    }
    return {
        "start_date": dates[0] if dates else None,
        "end_date": dates[-1] if dates else None,
        "days": [daily[day] for day in dates],
        "averages": averages,
    }


@app.get("/api/reports/weekly")
def weekly_report(user_id: int = Query(...), as_of: str = Query(...)):
    anchor = parse_report_date(as_of, "as_of")
    user = report_user(user_id)
    last_seven_start = anchor - timedelta(days=6)
    week_start = anchor - timedelta(days=anchor.weekday())
    daily = report_days(user_id, min(last_seven_start, week_start), anchor)
    return {
        "user": user,
        "as_of": anchor.isoformat(),
        "last_7_days": report_window(last_seven_start, anchor, daily),
        "current_week": report_window(week_start, anchor, daily),
    }


@app.get("/api/reports/foods")
def foods_report(
    user_id: int = Query(...),
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
):
    start = parse_report_date(from_date, "from")
    end = parse_report_date(to_date, "to")
    if start > end:
        raise HTTPException(400, "from must be on or before to")
    user = report_user(user_id)
    items = rows(
        "SELECT dl.date,dl.meal_type,dli.ingredient_name,dli.weight,dli.calories,"
        "dli.protein,dli.fat,dli.carbs,dli.sugar,dli.counts_as_added_sugar "
        "FROM daily_log_items dli JOIN daily_logs dl ON dl.id=dli.daily_log_id "
        "WHERE dl.user_id=? AND dl.date>=? AND dl.date<=? ORDER BY dl.date,dl.id,dli.id",
        (user_id, start.isoformat(), end.isoformat()),
    )
    for item in items:
        item["counts_as_added_sugar"] = bool(item["counts_as_added_sugar"])
    return {"user": user, "from": start.isoformat(), "to": end.isoformat(), "items": items}


@app.post("/api/logs")
def create_log(payload: LogIn):
    if not payload.items: raise HTTPException(400, "Add at least one ingredient")
    totals = {key: sum(getattr(i, key) for i in payload.items) for key in ("calories", "protein", "carbs", "sugar", "fat")}
    with connect() as db:
        cur = db.execute("INSERT INTO daily_logs(user_id,date,meal_type,total_calories,total_protein,total_carbs,total_sugar,total_fat) VALUES (?,?,?,?,?,?,?,?)", (payload.user_id, payload.date, payload.meal_type, *(totals[k] for k in ("calories", "protein", "carbs", "sugar", "fat")))); log_id = cur.lastrowid
        db.executemany("INSERT INTO daily_log_items(daily_log_id,ingredient_name,weight,calories,protein,carbs,sugar,fat,counts_as_added_sugar) VALUES (?,?,?,?,?,?,?,?,?)", [(log_id, i.name, i.weight, *(getattr(i, k) for k in ("calories", "protein", "carbs", "sugar", "fat")), int(i.counts_as_added_sugar)) for i in payload.items])
    return {"id": log_id}


@app.delete("/api/logs/{log_id}")
def delete_log(log_id: int):
    with connect() as db: db.execute("DELETE FROM daily_logs WHERE id=?", (log_id,))
    return {"ok": True}


@app.put("/api/logs/{log_id}")
def update_log(log_id: int, payload: LogIn):
    totals = {key: sum(getattr(i, key) for i in payload.items) for key in ("calories", "protein", "carbs", "sugar", "fat")}
    with connect() as db:
        if not db.execute("SELECT 1 FROM daily_logs WHERE id=?", (log_id,)).fetchone(): raise HTTPException(404, "Log not found")
        db.execute("UPDATE daily_logs SET user_id=?,date=?,meal_type=?,total_calories=?,total_protein=?,total_carbs=?,total_sugar=?,total_fat=? WHERE id=?", (payload.user_id, payload.date, payload.meal_type, *(totals[k] for k in ("calories", "protein", "carbs", "sugar", "fat")), log_id))
        db.execute("DELETE FROM daily_log_items WHERE daily_log_id=?", (log_id,))
        db.executemany("INSERT INTO daily_log_items(daily_log_id,ingredient_name,weight,calories,protein,carbs,sugar,fat,counts_as_added_sugar) VALUES (?,?,?,?,?,?,?,?,?)", [(log_id, i.name, i.weight, *(getattr(i, k) for k in ("calories", "protein", "carbs", "sugar", "fat")), int(i.counts_as_added_sugar)) for i in payload.items])
    return {"id": log_id}


@app.post("/api/logs/{log_id}/duplicate")
def duplicate_log(log_id: int, user_id: int):
    with connect() as db:
        source = db.execute("SELECT * FROM daily_logs WHERE id=?", (log_id,)).fetchone()
        if not source: raise HTTPException(404, "Log not found")
        items = db.execute("SELECT * FROM daily_log_items WHERE daily_log_id=?", (log_id,)).fetchall()
        cur = db.execute("INSERT INTO daily_logs(user_id,date,meal_type,total_calories,total_protein,total_carbs,total_sugar,total_fat) VALUES (?,?,?,?,?,?,?,?)", (user_id, source["date"], source["meal_type"], *(source[f"total_{k}"] for k in ("calories", "protein", "carbs", "sugar", "fat"))))
        db.executemany("INSERT INTO daily_log_items(daily_log_id,ingredient_name,weight,calories,protein,carbs,sugar,fat,counts_as_added_sugar) VALUES (?,?,?,?,?,?,?,?,?)", [(cur.lastrowid, i["ingredient_name"], i["weight"], *(i[k] for k in ("calories", "protein", "carbs", "sugar", "fat")), i["counts_as_added_sugar"]) for i in items])
    return {"id": cur.lastrowid}


NUTRIENTS = ("calories", "protein", "carbs", "sugar", "fat")


def build_recalculation(db, user_id, day):
    logs = db.execute("SELECT * FROM daily_logs WHERE user_id=? AND date=? ORDER BY id", (user_id, day)).fetchall()
    if not logs:
        raise HTTPException(404, "No meals found for that user and date")
    log_ids = [log["id"] for log in logs]
    placeholders = ",".join("?" for _ in log_ids)
    items = db.execute(f"SELECT * FROM daily_log_items WHERE daily_log_id IN ({placeholders}) ORDER BY id", log_ids).fetchall()
    matched = []
    skipped = []
    fingerprint_rows = []
    proposals = []
    for item in items:
        ingredient = db.execute("SELECT * FROM ingredients WHERE lower(trim(name))=lower(trim(?)) ORDER BY id LIMIT 1", (item["ingredient_name"],)).fetchone()
        if ingredient is None:
            skipped.append({"item_id": item["id"], "ingredient_name": item["ingredient_name"]})
            fingerprint_rows.append([item[k] for k in ("id", "daily_log_id", "ingredient_name", "weight", *NUTRIENTS)])
            continue
        nutrient_values = {key: ingredient[f"{key}_per_100g"] * item["weight"] / 100 for key in NUTRIENTS}
        proposal = {"item_id": item["id"], "daily_log_id": item["daily_log_id"], **nutrient_values}
        proposals.append(proposal)
        matched.append(proposal)
        fingerprint_rows.append([item[k] for k in ("id", "daily_log_id", "ingredient_name", "weight", *NUTRIENTS)] + [ingredient[k] for k in ("id", "name", *(f"{n}_per_100g" for n in NUTRIENTS))])

    before = {key: sum(log[f"total_{key}"] for log in logs) for key in NUTRIENTS}
    by_log = {log_id: {key: 0.0 for key in NUTRIENTS} for log_id in log_ids}
    for item in items:
        values = next((p for p in proposals if p["item_id"] == item["id"]), None)
        for key in NUTRIENTS:
            by_log[item["daily_log_id"]][key] += values[key] if values else item[key]
    after = {key: sum(v[key] for v in by_log.values()) for key in NUTRIENTS}
    for log in logs:
        fingerprint_rows.append([log[k] for k in ("id", "total_calories", "total_protein", "total_carbs", "total_sugar", "total_fat")])
    fingerprint = hashlib.sha256(json.dumps(fingerprint_rows, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
    return {"user_id": user_id, "date": day, "before": before, "after": after, "matched_count": len(matched), "skipped_count": len(skipped), "skipped": skipped, "fingerprint": fingerprint, "proposals": proposals, "log_totals": by_log}


@app.get("/api/users/{user_id}/logs/recalculate/preview")
def recalculate_preview(user_id: int, date: str = Query(...)):
    with connect() as db:
        result = build_recalculation(db, user_id, date)
    result.pop("proposals")
    result.pop("log_totals")
    return result


@app.post("/api/users/{user_id}/logs/recalculate/confirm")
def recalculate_confirm(user_id: int, payload: RecalculateConfirm, date: str = Query(...)):
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        result = build_recalculation(db, user_id, date)
        if result["fingerprint"] != payload.fingerprint:
            raise HTTPException(409, "The day changed after the preview. Refresh the preview before confirming.")
        for proposal in result["proposals"]:
            db.execute("UPDATE daily_log_items SET calories=?,protein=?,carbs=?,sugar=?,fat=? WHERE id=?", (*(proposal[key] for key in NUTRIENTS), proposal["item_id"]))
        for log_id, totals in result["log_totals"].items():
            db.execute("UPDATE daily_logs SET total_calories=?,total_protein=?,total_carbs=?,total_sugar=?,total_fat=? WHERE id=?", (*(totals[key] for key in NUTRIENTS), log_id))
    return {"date": date, "updated_count": result["matched_count"], "skipped_count": result["skipped_count"], "skipped": result["skipped"], "totals": result["after"]}

