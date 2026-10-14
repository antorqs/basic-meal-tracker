from contextlib import asynccontextmanager
from datetime import date as date_type
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
        CREATE TABLE IF NOT EXISTS user_targets (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, effective_date TEXT NOT NULL, target_calories INTEGER NOT NULL, target_protein INTEGER NOT NULL, UNIQUE(user_id, effective_date));
        CREATE TABLE IF NOT EXISTS ingredients (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, calories_per_100g REAL NOT NULL, protein_per_100g REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS meals (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS meal_items (id INTEGER PRIMARY KEY, meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE, ingredient_id INTEGER NOT NULL REFERENCES ingredients(id), default_weight REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS daily_logs (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, date TEXT NOT NULL, meal_type TEXT NOT NULL, total_calories REAL NOT NULL DEFAULT 0, total_protein REAL NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS daily_log_items (id INTEGER PRIMARY KEY, daily_log_id INTEGER NOT NULL REFERENCES daily_logs(id) ON DELETE CASCADE, ingredient_name TEXT NOT NULL, weight REAL NOT NULL, calories REAL NOT NULL, protein REAL NOT NULL);
        """)
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            db.executemany("INSERT INTO users(name,target_calories,target_protein) VALUES (?,?,?)", [("Alex", 2200, 160), ("Sam", 1800, 120)])
        for user in db.execute("SELECT id,target_calories,target_protein FROM users").fetchall():
            db.execute("INSERT OR IGNORE INTO user_targets(user_id,effective_date,target_calories,target_protein) VALUES (?,?,?,?)", (user["id"], "1900-01-01", user["target_calories"], user["target_protein"]))
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


class ItemIn(BaseModel):
    name: str = Field(min_length=1)
    weight: float = Field(gt=0)
    calories: float = Field(ge=0)
    protein: float = Field(ge=0)


class MealIn(BaseModel):
    name: str = Field(min_length=1)
    items: list[ItemIn]


class LogIn(BaseModel):
    user_id: int
    date: str
    meal_type: str
    items: list[ItemIn]


def rows(sql, args=()):
    with connect() as db:
        return [dict(r) for r in db.execute(sql, args).fetchall()]


@app.get("/")
def index():
    return FileResponse(ROOT / "static/index.html")


@app.get("/api/users")
def users():
    return rows("SELECT id,name FROM users ORDER BY id")


@app.put("/api/users/{user_id}")
def update_user(user_id: int, payload: dict):
    with connect() as db:
        if not db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone(): raise HTTPException(404, "User not found")
        db.execute("UPDATE users SET name=COALESCE(?,name) WHERE id=?", (payload.get("name"), user_id))
        if payload.get("target_calories") is not None and payload.get("target_protein") is not None:
            effective = payload.get("effective_date") or str(date_type.today())
            db.execute("INSERT INTO user_targets(user_id,effective_date,target_calories,target_protein) VALUES (?,?,?,?) ON CONFLICT(user_id,effective_date) DO UPDATE SET target_calories=excluded.target_calories,target_protein=excluded.target_protein", (user_id, effective, payload["target_calories"], payload["target_protein"]))
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
            cur = db.execute("INSERT INTO ingredients(name,calories_per_100g,protein_per_100g) VALUES (?,?,?)", (payload.name, payload.calories_per_100g, payload.protein_per_100g))
            return {"id": cur.lastrowid, **payload.model_dump()}
    except sqlite3.IntegrityError: raise HTTPException(409, "Ingredient already exists")


@app.put("/api/ingredients/{ingredient_id}")
def update_ingredient(ingredient_id: int, payload: IngredientIn):
    try:
        with connect() as db:
            if not db.execute("SELECT 1 FROM ingredients WHERE id=?", (ingredient_id,)).fetchone(): raise HTTPException(404, "Ingredient not found")
            db.execute("UPDATE ingredients SET name=?,calories_per_100g=?,protein_per_100g=? WHERE id=?", (payload.name, payload.calories_per_100g, payload.protein_per_100g, ingredient_id))
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
            ing = db.execute("SELECT id FROM ingredients WHERE name=?", (item.name,)).fetchone()
            if not ing: raise HTTPException(400, f"Unknown ingredient: {item.name}")
            db.execute("INSERT INTO meal_items(meal_id,ingredient_id,default_weight) VALUES (?,?,?)", (meal_id, ing["id"], item.weight))
    return {"id": meal_id, "name": payload.name}


def summary(user_id, day):
    user = rows("SELECT * FROM users WHERE id=?", (user_id,))
    if not user: raise HTTPException(404, "User not found")
    logs = rows("SELECT * FROM daily_logs WHERE user_id=? AND date=? ORDER BY id", (user_id, day))
    for log in logs: log["items"] = rows("SELECT * FROM daily_log_items WHERE daily_log_id=? ORDER BY id", (log["id"],))
    consumed = {"calories": sum(x["total_calories"] for x in logs), "protein": sum(x["total_protein"] for x in logs)}
    u = user[0]
    target = rows("SELECT target_calories,target_protein,effective_date FROM user_targets WHERE user_id=? AND effective_date<=? ORDER BY effective_date DESC LIMIT 1", (user_id, day))
    active = target[0] if target else {"target_calories": 2000, "target_protein": 140, "effective_date": None}
    u.update(active)
    return {"user": u, "date": day, "consumed": consumed, "remaining": {"calories": max(0, active["target_calories"] - consumed["calories"]), "protein": max(0, active["target_protein"] - consumed["protein"])}, "logs": logs}


@app.get("/api/summary")
def get_summary(user_id: int = 1, date: str | None = None):
    return summary(user_id, date or str(date_type.today()))


@app.post("/api/logs")
def create_log(payload: LogIn):
    if not payload.items: raise HTTPException(400, "Add at least one ingredient")
    calories = sum(i.calories for i in payload.items); protein = sum(i.protein for i in payload.items)
    with connect() as db:
        cur = db.execute("INSERT INTO daily_logs(user_id,date,meal_type,total_calories,total_protein) VALUES (?,?,?,?,?)", (payload.user_id, payload.date, payload.meal_type, calories, protein)); log_id = cur.lastrowid
        db.executemany("INSERT INTO daily_log_items(daily_log_id,ingredient_name,weight,calories,protein) VALUES (?,?,?,?,?)", [(log_id, i.name, i.weight, i.calories, i.protein) for i in payload.items])
    return {"id": log_id}


@app.delete("/api/logs/{log_id}")
def delete_log(log_id: int):
    with connect() as db: db.execute("DELETE FROM daily_logs WHERE id=?", (log_id,))
    return {"ok": True}


@app.put("/api/logs/{log_id}")
def update_log(log_id: int, payload: LogIn):
    calories = sum(i.calories for i in payload.items); protein = sum(i.protein for i in payload.items)
    with connect() as db:
        if not db.execute("SELECT 1 FROM daily_logs WHERE id=?", (log_id,)).fetchone(): raise HTTPException(404, "Log not found")
        db.execute("UPDATE daily_logs SET user_id=?,date=?,meal_type=?,total_calories=?,total_protein=? WHERE id=?", (payload.user_id, payload.date, payload.meal_type, calories, protein, log_id))
        db.execute("DELETE FROM daily_log_items WHERE daily_log_id=?", (log_id,))
        db.executemany("INSERT INTO daily_log_items(daily_log_id,ingredient_name,weight,calories,protein) VALUES (?,?,?,?,?)", [(log_id, i.name, i.weight, i.calories, i.protein) for i in payload.items])
    return {"id": log_id}


@app.post("/api/logs/{log_id}/duplicate")
def duplicate_log(log_id: int, user_id: int):
    with connect() as db:
        source = db.execute("SELECT * FROM daily_logs WHERE id=?", (log_id,)).fetchone()
        if not source: raise HTTPException(404, "Log not found")
        items = db.execute("SELECT * FROM daily_log_items WHERE daily_log_id=?", (log_id,)).fetchall()
        cur = db.execute("INSERT INTO daily_logs(user_id,date,meal_type,total_calories,total_protein) VALUES (?,?,?,?,?)", (user_id, source["date"], source["meal_type"], source["total_calories"], source["total_protein"]))
        db.executemany("INSERT INTO daily_log_items(daily_log_id,ingredient_name,weight,calories,protein) VALUES (?,?,?,?,?)", [(cur.lastrowid, i["ingredient_name"], i["weight"], i["calories"], i["protein"]) for i in items])
    return {"id": cur.lastrowid}

