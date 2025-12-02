import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
import json
import time
import threading
import sqlite3
import cv2
import numpy as np
from datetime import datetime
from person_detector import PersonDetector

# ---------------------------
# Config
# ---------------------------
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "esp32/data"  # รับ JSON จาก ESP32

KY037_PIN = 22         # Digital output of KY-037 -> GPIO22 (ปรับตามต่อจริง)
LED_PIN = 17           # สถานะ LED
BUZZER_PIN = 27        # Buzzer (ใช้ PWM)

DB_PATH = "/home/earnt/Final_Project/gateway_sensor_log.db"

# Safe ranges (ปรับได้)
TEMP_SAFE_MIN = 15.0
TEMP_SAFE_MAX = 37.0
HUM_SAFE_MIN  = 20.0
HUM_SAFE_MAX  = 70.0

# Buzzer PWM params
BUZZER_FREQ = 1800

# Alert duration
ALERT_DURATION_SECONDS = 3  # Keep alert active for minimum 5 seconds

# Camera detection params
PERSON_DETECT_INTERVAL = 1.0  # วินาทีระหว่างการตรวจซ้ำ

# ---------------------------
# GPIO init
# ---------------------------
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(KY037_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # Add pull-down resistor
GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
buzzer_pwm = GPIO.PWM(BUZZER_PIN, BUZZER_FREQ)
buzzer_running = False

# ---------------------------
# DB init (SQLite)
# ---------------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS samples (
    timestamp DATE,
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

# ---------------------------
# Global state
# ---------------------------
latest = {
    "temperature": None,
    "humidity": None,
    "button": 0,
    "abnormal_movement": 0  # Changed from "abnormalMovement" to match usage
}
sound_alert = 0
person_present = 0
current_status = "NORMAL"
alert_start_time = 0
alert_hold_until = 0
beep_state = False
beep_last_toggle = 0
lock = threading.Lock()

# ---------------------------
# Camera / Person detection using PersonDetector
# ---------------------------
detector = None

def person_detector_thread():
    global person_present, detector
    
    # สร้าง PersonDetector object
    try:
        detector = PersonDetector(model_path='yolo11n.pt')
        detector.start()  # เริ่ม background thread ของ detector
        print("[GATEWAY] PersonDetector initialized successfully")
    except Exception as e:
        print(f"[GATEWAY] Failed to initialize PersonDetector: {e}")
        print("[GATEWAY] Falling back to simple detection")
        # Fallback ใช้ Haar cascade เหมือนเดิม
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_fullbody.xml")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("WARNING: Camera not opened. Person detection disabled.")
            return
        while True:
            ret, frame = cap.read()
            if not ret:
                person_present = 0
                time.sleep(PERSON_DETECT_INTERVAL)
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            people = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(60,60))
            with lock:
                person_present = 1 if len(people) > 0 else 0
            time.sleep(PERSON_DETECT_INTERVAL)
        return
    
    # ใช้ PersonDetector (YOLO) - อ่านค่าจาก detector.person_detected
    while True:
        if detector:
            with lock:
                person_present = 1 if detector.person_detected > 0 else 0
        time.sleep(PERSON_DETECT_INTERVAL)

# ---------------------------
# KY-037 reading thread (digital pin)
# ---------------------------
def ky037_watcher_thread():
    global sound_alert
    while True:
        try:
            val = GPIO.input(KY037_PIN)  # 0 or 1
            with lock:
                sound_alert = 1 if val == 1 else 0
        except Exception as e:
            print(f"[KY037] Error reading pin: {e}")
            time.sleep(1)
            continue
        # short sleep to avoid busy loop
        time.sleep(0.05)

# ---------------------------
# MQTT callbacks
# ---------------------------
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Connected to MQTT broker")
        client.subscribe(MQTT_TOPIC)
    else:
        print("MQTT connect failed rc=", rc)

def on_message(client, userdata, msg):
    global latest
    try:
        payload = json.loads(msg.payload.decode())
    except Exception as e:
        print("Invalid JSON payload:", e)
        return

    # payload expected structure: { "temperature":..., "humidity":..., "buttonPressed":0/1, "abnormalMovement":0/1 }
    with lock:
        latest["temperature"] = payload.get("temperature", latest["temperature"])
        latest["humidity"] = payload.get("humidity", latest["humidity"])
        latest["button"] = int(payload.get("buttonPressed", latest["button"]))
        # Map camelCase from ESP32 to snake_case for internal use
        latest["abnormal_movement"] = int(payload.get("abnormalMovement", latest["abnormal_movement"]))

# ---------------------------
# Fusion logic (ตรงตามที่คุณขอ)
# ---------------------------
def evaluate_fusion(btn, abnormal_movement, person_present, sound_alert, temp, hum):
    # IF button == 1 → EMERGENCY
    if btn == 1:
        return "EMERGENCY"
    # ELIF abnormal_movement == 1 AND person_present == 1 → EMERGENCY
    if abnormal_movement == 1 and person_present == 1:
        return "EMERGENCY"
    if person_present == 0:
        return "EMERGENCY"
    # ELIF sound_alert == 1 → WARNING
    if sound_alert == 1:
        return "WARNING"
    # ELIF temp/humidity นอกช่วงปลอดภัย → WARNING
    if temp is not None:
        if not (TEMP_SAFE_MIN <= temp <= TEMP_SAFE_MAX):
            return "WARNING"
    if hum is not None:
        if not (HUM_SAFE_MIN <= hum <= HUM_SAFE_MAX):
            return "WARNING"
    # ELSE → NORMAL
    return "NORMAL"

# ---------------------------
# Actuator control (runs in separate thread)
# ---------------------------
def actuator_control_thread():
    global buzzer_running, current_status
    last_status = "NORMAL"
    
    while True:
        status = current_status
        
        # Only change actuators when status changes
        if status != last_status:
            if status == "NORMAL":
                GPIO.output(LED_PIN, GPIO.LOW)
                if buzzer_running:
                    try:
                        buzzer_pwm.stop()
                    except:
                        pass
                    buzzer_running = False
                    
            # elif status == "WARNING":
            #     GPIO.output(LED_PIN, GPIO.HIGH)
            #     if not buzzer_running:
            #         try:
            #             buzzer_pwm.stop()
            #         except:
            #             pass
            #         buzzer_running = False
            
            elif status in ["WARNING", "EMERGENCY"]:
                GPIO.output(LED_PIN, GPIO.HIGH)
                if not buzzer_running:
                    try:
                        buzzer_pwm.start(75)
                        buzzer_running = True
                    except:
                        pass
            
            last_status = status
        
        # time.sleep(0.01)  # Fast response time

# ---------------------------
# Logger (DB)
# ---------------------------
def log_sample(timestamp, temp, hum, btn, movement_abn, sound, person, status):
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

# ---------------------------
# Main loop
# ---------------------------
def main_loop():
    global current_status, alert_start_time, alert_hold_until
    print("Starting main loop...")
    try:
        while True:
            with lock:
                temp = latest["temperature"]
                hum = latest["humidity"]
                btn = latest["button"]
                movement_abn = latest["abnormal_movement"]
                sound = sound_alert
                person = person_present

            now = time.time()
            status = evaluate_fusion(btn, movement_abn, person, sound, temp, hum)
            
            # If alert triggered, set hold duration
            if status in ["WARNING", "EMERGENCY"]:
                if current_status == "NORMAL" or now >= alert_hold_until:
                    alert_start_time = now
                    alert_hold_until = now + ALERT_DURATION_SECONDS
                    print(f"[ALERT] {status} triggered - holding for {ALERT_DURATION_SECONDS}s")
            
            # Keep alert active until hold time expires
            if now < alert_hold_until:
                # Override status to keep alert active
                if status == "NORMAL":
                    status = current_status  # Keep previous alert status
            
            current_status = status

            timestamp = datetime.now()
            # log to DB
            log_sample(timestamp, temp, hum, btn, movement_abn, sound, person, status)

            # optional: print short summary
            print(f"{timestamp} | status={status} | btn={btn} move={movement_abn} person={person} sound={sound} temp={temp} hum={hum}")

            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        # ทำความสะอาด PersonDetector
        if detector:
            detector.stop()
            print("[GATEWAY] PersonDetector stopped")
        # Stop PWM before cleanup
        try:
            if buzzer_running:
                buzzer_pwm.stop()
        except Exception as e:
            print(f"[GATEWAY] PWM stop error (ignored): {e}")
        try:
            GPIO.cleanup()
        except Exception as e:
            print(f"[GATEWAY] GPIO cleanup error (ignored): {e}")
        conn.close()
        print("[GATEWAY] System shutdown complete")

# ---------------------------
# Start threads & MQTT
# ---------------------------
if __name__ == "__main__":
    # start camera thread
    cam_thread = threading.Thread(target=person_detector_thread, daemon=True)
    cam_thread.start()

    # start KY-037 watcher
    ky_thread = threading.Thread(target=ky037_watcher_thread, daemon=True)
    ky_thread.start()
    
    # start actuator control thread
    actuator_thread = threading.Thread(target=actuator_control_thread, daemon=True)
    actuator_thread.start()

    # setup mqtt with callback API version 2
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="PiGatewaySubscriber"
    )
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    # run main loop (blocking)
    main_loop()