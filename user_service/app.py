import os
import sqlite3
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

DB = os.getenv("DB_PATH", "users.db")
app = FastAPI(title="User Service", description="Клієнти сервісу онлайн-замовлення їжі")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"], allow_methods=["*"], allow_headers=["*"])

@contextmanager
def db():
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()

with db() as con:
    con.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, phone TEXT NOT NULL)")
    if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        con.execute(
            "INSERT INTO users(name, email, phone) VALUES(?, ?, ?)",
            ("Олена Коваль", "olena@example.com", "+380501234567"),
        )

class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=200)
    phone: str = Field(min_length=5, max_length=30)

class UserUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=200)
    phone: str = Field(min_length=5, max_length=30)

@app.get("/health")
def health(): return {"status": "ok", "service": "user-service"}

@app.post("/users", status_code=201)
def create_user(payload: UserCreate):
    try:
        with db() as con:
            cur = con.execute("INSERT INTO users(name,email,phone) VALUES(?,?,?)", (payload.name, payload.email, payload.phone))
            return {"id": cur.lastrowid, **payload.model_dump()}
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Користувач з таким email вже існує")

@app.get("/users")
def list_users():
    with db() as con: return [dict(r) for r in con.execute("SELECT * FROM users ORDER BY id")]

@app.get("/users/{user_id}")
def get_user(user_id: int):
    with db() as con: row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if row is None: raise HTTPException(404, "Користувача не знайдено")
    return dict(row)

@app.put("/users/{user_id}")
def update_user(user_id: int, payload: UserUpdate):
    try:
        with db() as con:
            cur = con.execute(
                "UPDATE users SET name=?, email=?, phone=? WHERE id=?",
                (payload.name, payload.email, payload.phone, user_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "Користувача не знайдено")
            return {"id": user_id, **payload.model_dump()}
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Користувач з таким email вже існує")
