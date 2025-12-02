from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import os
import paho.mqtt.client as mqtt
import threading
import asyncio
import json
import time
import sys

load_dotenv()

app = FastAPI()

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://172.20.10.2:5173",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.getenv("DB_PATH", "/home/earnt/Final_Project/data.db")

# MQTT Config
MQTT_BROKER = "localhost"
MQTT_PORT = 1883

# Global state for MQTT
mqtt_client = None
device_status = {
    "esp32_online": False,
    "pi_online": False,
    "esp32_control": True,
    "pi_control": True
}
status_lock = threading.Lock()

# WebSocket connections
active_connections = []
ws_lock = threading.Lock()

# Track last seen timestamps for timeout detection
last_seen = {
    "esp32": 0,
    "pi": 0
}
TIMEOUT_SECONDS = 10  # Consider device offline after 10 seconds

# MQTT Callbacks
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("[MQTT Bridge] Connected to MQTT broker")
        client.subscribe("esp32/status")
        client.subscribe("pi/status")
        client.subscribe("esp32/control")
        client.subscribe("pi/control")
        client.subscribe("esp32/data")  # Subscribe to data to detect ESP32 activity
    else:
        print(f"[MQTT Bridge] Connection failed rc={rc}")

def on_message(client, userdata, msg):
    global device_status, last_seen
    topic = msg.topic
    payload = msg.payload.decode()
    
    changed = False
    with status_lock:
        old_status = device_status.copy()
        
        if topic == "esp32/status":
            new_val = (payload.lower() == "true" or payload == "1")
            if device_status["esp32_online"] != new_val:
                device_status["esp32_online"] = new_val
                changed = True
                print(f"[MQTT Bridge] ESP32 status: {'ONLINE' if new_val else 'OFFLINE'}")
            last_seen["esp32"] = time.time()
            
        elif topic == "esp32/data":
            # ESP32 is sending data, so it's online
            if not device_status["esp32_online"]:
                device_status["esp32_online"] = True
                changed = True
                print(f"[MQTT Bridge] ESP32 status: ONLINE (data received)")
            last_seen["esp32"] = time.time()
            
        elif topic == "pi/status":
            new_val = (payload.lower() == "true" or payload == "1")
            if device_status["pi_online"] != new_val:
                device_status["pi_online"] = new_val
                changed = True
                print(f"[MQTT Bridge] Pi status: {'ONLINE' if new_val else 'OFFLINE'}")
            last_seen["pi"] = time.time()
            
        elif topic == "esp32/control":
            new_val = (payload.lower() == "true" or payload == "1")
            if device_status["esp32_control"] != new_val:
                device_status["esp32_control"] = new_val
                changed = True
                print(f"[MQTT Bridge] ESP32 control: {'ENABLED' if new_val else 'DISABLED'}")
            
        elif topic == "pi/control":
            new_val = (payload.lower() == "true" or payload == "1")
            if device_status["pi_control"] != new_val:
                device_status["pi_control"] = new_val
                changed = True
                print(f"[MQTT Bridge] Pi control: {'ENABLED' if new_val else 'DISABLED'}")

# Timeout checker thread
def check_device_timeouts():
    global device_status
    print("[TIMEOUT] Device timeout checker started")
    while True:
        time.sleep(2)  # Check every 2 seconds
        current_time = time.time()
        
        changed = False
        with status_lock:
            # Check ESP32 timeout
            if device_status["esp32_online"] and (current_time - last_seen["esp32"]) > TIMEOUT_SECONDS:
                device_status["esp32_online"] = False
                changed = True
                print(f"[TIMEOUT] ESP32 marked offline (no activity for {TIMEOUT_SECONDS}s)")
            
            # Check Pi timeout
            if device_status["pi_online"] and (current_time - last_seen["pi"]) > TIMEOUT_SECONDS:
                device_status["pi_online"] = False
                changed = True
                print(f"[TIMEOUT] Pi marked offline (no activity for {TIMEOUT_SECONDS}s)")

# Initialize MQTT
def init_mqtt():
    global mqtt_client
    mqtt_client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="WebDashboardBridge"
    )
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print("[MQTT Bridge] Started MQTT client")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# WebSocket broadcast functions
async def broadcast_device_status():
    with ws_lock:
        if not active_connections:
            return
        
        message = json.dumps({
            "type": "device_status",
            "data": device_status
        })
        
        disconnected = []
        for ws in active_connections:
            try:
                await ws.send_text(message)
            except:
                disconnected.append(ws)
        
        for ws in disconnected:
            active_connections.remove(ws)

async def broadcast_latest_data():
    with ws_lock:
        if not active_connections:
            return
    
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM samples ORDER BY ts DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        
        if row:
            message = json.dumps({
                "type": "sensor_data",
                "data": dict(row)
            })
            
            disconnected = []
            with ws_lock:
                for ws in active_connections:
                    try:
                        await ws.send_text(message)
                    except:
                        disconnected.append(ws)
                
                for ws in disconnected:
                    active_connections.remove(ws)
    except Exception as e:
        print(f"[WebSocket] Broadcast error: {e}")

# Periodic broadcast thread
def periodic_broadcast_worker():
    print("[WebSocket] Periodic broadcast task started")
    while True:
        time.sleep(1)  # Broadcast every 1 second
        asyncio.run(broadcast_latest_data())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    with ws_lock:
        active_connections.append(websocket)
    print(f"[WebSocket] Client connected. Total: {len(active_connections)}")
    
    # Send initial device status
    with status_lock:
        await websocket.send_text(json.dumps({
            "type": "device_status",
            "data": device_status.copy()
        }))
    
    # Send initial sensor data
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM samples ORDER BY ts DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        
        if row:
            await websocket.send_text(json.dumps({
                "type": "sensor_data",
                "data": dict(row)
            }))
    except Exception as e:
        print(f"[WebSocket] Error sending initial data: {e}")
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        with ws_lock:
            if websocket in active_connections:
                active_connections.remove(websocket)
        print(f"[WebSocket] Client disconnected. Total: {len(active_connections)}")

@app.get("/api/device-status")
def get_device_status():
    with status_lock:
        return device_status.copy()

@app.post("/api/control/esp32")
def control_esp32(enabled: bool):
    if mqtt_client and mqtt_client.is_connected():
        payload = "true" if enabled else "false"
        mqtt_client.publish("esp32/control", payload)
        with status_lock:
            device_status["esp32_control"] = enabled
        return {"success": True, "esp32_control": enabled}
    return {"success": False, "error": "MQTT not connected"}

@app.post("/api/control/pi")
def control_pi(enabled: bool):
    if mqtt_client and mqtt_client.is_connected():
        payload = "true" if enabled else "false"
        mqtt_client.publish("pi/control", payload)
        with status_lock:
            device_status["pi_control"] = enabled
        return {"success": True, "pi_control": enabled}
    return {"success": False, "error": "MQTT not connected"}

@app.post("/api/control/servo")
def control_servo(turn_on: bool):
    if mqtt_client and mqtt_client.is_connected():
        payload = "on" if turn_on else "off"
        mqtt_client.publish("pi/servo", payload)
        return {"success": True, "light_on": turn_on}
    return {"success": False, "error": "MQTT not connected"}

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
    cur.execute("SELECT * FROM samples ORDER BY ts DESC LIMIT 100")
    rows = cur.fetchall()
    conn.close()

    return [dict(r) for r in rows]

# Startup initialization
print("[STARTUP] Initializing backend...", flush=True)

# Delete old database and create fresh one
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print("[DB] Deleted old database", flush=True)

# Create new database
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS samples (
    ts TEXT,
    temperature REAL,
    humidity REAL,
    button INTEGER,
    abnormal_movement INTEGER,
    sound_alert INTEGER,
    person_present INTEGER,
    status TEXT
)
""")
conn.commit()
conn.close()
print("[DB] Created fresh database", flush=True)

# Start MQTT client
init_mqtt()

# Start timeout checker thread
timeout_thread = threading.Thread(target=check_device_timeouts, daemon=True)
timeout_thread.start()
print("[TIMEOUT] Started device timeout checker", flush=True)

# Start periodic broadcast in background thread
broadcast_thread = threading.Thread(target=periodic_broadcast_worker, daemon=True)
broadcast_thread.start()
print("[WebSocket] Started periodic broadcast thread", flush=True)
print("[STARTUP] Backend ready!", flush=True)

