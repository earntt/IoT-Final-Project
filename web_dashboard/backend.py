from fastapi import FastAPI, WebSocket,WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import os
import asyncio

app = FastAPI()
load_dotenv(os.path.join("..\.env"))

connected_clients = []

origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.getenv("DB_PATH")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    print("WS Connected")

    try:
        last_ts = None
        while True:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM samples ORDER BY timestamp DESC LIMIT 1")
            row = cur.fetchone()
            conn.close()
            
            if row and row["timestamp"] != last_ts:
                last_ts = row["timestamp"]
                await websocket.send_json(dict(row))
            
            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        print("WS Disconnected")
        connected_clients.remove(websocket)


@app.get("/api/history")
def get_history():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM samples WHERE timestamp ORDER BY timestamp DESC",
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
    status: str,
    background_tasks: BackgroundTasks
):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO samples VALUES (?,?,?,?,?,?,?,?)""",
                (timestamp,
                 temp,
                 hum,
                 btn,
                 movement_abn,
                 sound,
                 person,
                 status))
    conn.commit()
    conn.close()

    latest_data = {
        "timestamp": timestamp,
        "temp": temp,
        "hum": hum,
        "btn": btn,
        "movement_abn": movement_abn,
        "sound": sound,
        "person": person,
        "status": status,
    }
    
    background_tasks.add_task(broadcast, latest_data)

    return {"message": "sample inserted", "timestamp": timestamp}

async def broadcast(data: dict):
    dead_clients = []
    for ws in connected_clients:
        try:
            await ws.send_json(data)  # send_json เพื่อส่ง dict
        except:
            dead_clients.append(ws)

    for ws in dead_clients:
        connected_clients.remove(ws)

