from fastapi import FastAPI
from fastapi.responses import JSONResponse
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import os

app = FastAPI()
load_dotenv(os.path.join("..\.env"))

DB_PATH = os.getenv("DB_PATH")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/api/latest")
def get_latest():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM samples ORDER BY ts DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()

    if not row:
        return JSONResponse({"error": "no data"}, status_code=404)

    return dict(row)

@app.get("/api/history")
def get_history():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM samples WHERE ts ORDER BY ts ASC",
    )
    rows = cur.fetchall()
    conn.close()

    return [dict(r) for r in rows]

@app.post("/api/insert")
def insert_sample(
    temp: float,
    hum: float,
    btn: int,
    movement_abn: int,
    sound: int,
    person: int,
    status: str
):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO samples VALUES (?,?,?,?,?,?,?,?)""",
                (ts,
                 temp,
                 hum,
                 btn,
                 movement_abn,
                 sound,
                 person,
                 status))
    conn.commit()
    conn.close()

    return {"message": "sample inserted", "ts": ts}