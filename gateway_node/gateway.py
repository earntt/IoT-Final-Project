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
MQTT_TOPIC_DATA = "esp32/data"  # รับ JSON จาก ESP32
MQTT_TOPIC_STATUS = "esp32/status"  # ESP32 online/offline status
MQTT_TOPIC_CONTROL = "esp32/control"  # Control ESP32 sensor reading
MQTT_TOPIC_PI_STATUS = "pi/status"  # Pi online/offline status
MQTT_TOPIC_PI_CONTROL = "pi/control"  # Control Pi processing
MQTT_TOPIC_SERVO = "pi/servo"  # Control servo motor (on/off)

KY037_PIN = 22         # Digital output of KY-037 -> GPIO22 (ปรับตามต่อจริง)
LED_PIN = 17           # สถานะ LED
BUZZER_PIN = 27        # Buzzer (ใช้ PWM)
SERVO_PIN = 18         # Servo motor for light switch control

DB_PATH = "/home/earnt/Final_Project/data.db"

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
GPIO.setup(SERVO_PIN, GPIO.OUT, initial=GPIO.LOW)
buzzer_running = False
buzzer_pwm = None
servo_pwm = None
try:
    buzzer_pwm = GPIO.PWM(BUZZER_PIN, BUZZER_FREQ)
    servo_pwm = GPIO.PWM(SERVO_PIN, 50)  # 50Hz for servo (standard)
    servo_pwm.start(0)  # Start with 0 duty cycle
    print("[SERVO] PWM initialized successfully")
    
    # Reset servo to OFF position (0°)
    print("[SERVO] Resetting servo to 0°...")
    servo_pwm.ChangeDutyCycle(2.5)  # 0° = 2.5% duty
    time.sleep(0.5)
    servo_pwm.ChangeDutyCycle(0)
    
    # Also reset the state variable
    light_switch_on = False
    print("[SERVO] Servo reset complete - position: 0° (OFF), state: OFF")
except Exception as e:
    print(f"[WARNING] PWM initialization failed: {e}")

# ---------------------------
# DB init (SQLite)
# ---------------------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
esp32_online = False
pi_control_enabled = True  # Default: enabled
light_switch_on = False  # Servo position: False=OFF, True=ON
alert_start_time = 0
alert_hold_until = 0
beep_state = False
beep_last_toggle = 0
lock = threading.Lock()
system_running = True  # Global flag to stop all threads

# ---------------------------
# Servo Motor Control
# ---------------------------
def set_servo_angle(angle):
    """Set servo angle (0-180 degrees)
    
    Simple formula: duty_cycle = 2.5 + (angle / 18)
    - 0° = 2.5% duty
    - 90° = 7.5% duty
    - 180° = 12.5% duty
    """
    if servo_pwm is None:
        print("[SERVO] PWM not initialized")
        return
    
    # Clamp angle to 0-180°
    if angle < 0:
        angle = 0
    elif angle > 180:
        angle = 180
    
    # Simple duty cycle calculation
    duty = 2.5 + (angle / 18.0)
    
    try:
        # Stop any previous signal first
        servo_pwm.ChangeDutyCycle(0)
        time.sleep(0.1)
        
        # Send position signal
        servo_pwm.ChangeDutyCycle(duty)
        print(f"[SERVO] Moving to {angle}° (duty: {duty:.2f}%)")
        time.sleep(0.8)  # Longer wait for servo to reach position
        
        # Stop signal to prevent jitter
        servo_pwm.ChangeDutyCycle(0)
        time.sleep(0.1)
        print(f"[SERVO] Done")
    except Exception as e:
        print(f"[SERVO] Error: {e}")

servo_lock = threading.Lock()  # Prevent concurrent servo movements

def control_light_switch(turn_on):
    """Control light switch via servo motor
    
    Adjust OFF_ANGLE and ON_ANGLE as needed (0-180°)
    """
    global light_switch_on
    
    OFF_ANGLE = 0      # OFF position
    ON_ANGLE = 90      # ON position
    
    with servo_lock:  # Ensure only one servo command at a time
        if turn_on and not light_switch_on:
            set_servo_angle(ON_ANGLE)
            light_switch_on = True
            print(f"[SERVO] Light switch ON ({ON_ANGLE}°)")
        elif not turn_on and light_switch_on:
            set_servo_angle(OFF_ANGLE)
            light_switch_on = False
            print(f"[SERVO] Light switch OFF ({OFF_ANGLE}°)")
        else:
            print(f"[SERVO] Already {'ON' if light_switch_on else 'OFF'}")

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
        while system_running:
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
    while system_running:
        if detector:
            with lock:
                person_present = 1 if detector.person_detected > 0 else 0
        time.sleep(PERSON_DETECT_INTERVAL)

# ---------------------------
# KY-037 reading thread (digital pin)
# ---------------------------
def ky037_watcher_thread():
    global sound_alert
    print("[KY037] Sound sensor thread starting...")
    time.sleep(1)  # Wait for GPIO to stabilize
    print("[KY037] Thread active")
    
    while system_running:
        try:
            val = GPIO.input(KY037_PIN)  # 0 or 1
            with lock:
                old_val = sound_alert
                sound_alert = 1 if val == 1 else 0
                # Log only when value changes
                if old_val != sound_alert and sound_alert == 1:
                    print(f"[KY037] Sound detected! Pin value: {val}")
        except Exception as e:
            if system_running:  # Only print error if still running
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
        client.subscribe(MQTT_TOPIC_DATA)
        client.subscribe(MQTT_TOPIC_STATUS)
        client.subscribe(MQTT_TOPIC_CONTROL)
        client.subscribe(MQTT_TOPIC_PI_CONTROL)
        client.subscribe(MQTT_TOPIC_SERVO)
        print(f"Subscribed to: {MQTT_TOPIC_DATA}, {MQTT_TOPIC_STATUS}, {MQTT_TOPIC_CONTROL}, {MQTT_TOPIC_PI_CONTROL}, {MQTT_TOPIC_SERVO}")
        
        # Publish Pi online status with retained flag
        client.publish(MQTT_TOPIC_PI_STATUS, "true", retain=True)
        print("Published Pi status: online")
    else:
        print("MQTT connect failed rc=", rc)

def on_message(client, userdata, msg):
    global latest, esp32_online, pi_control_enabled, light_switch_on
    
    topic = msg.topic
    payload_str = msg.payload.decode()
    
    # Handle Servo control
    if topic == MQTT_TOPIC_SERVO:
        turn_on = (payload_str.lower() == "on" or payload_str == "1" or payload_str.lower() == "true")
        print(f"[MQTT] Servo command received: {'ON' if turn_on else 'OFF'}")
        control_light_switch(turn_on)
        return
    
    # Handle ESP32 status
    if topic == MQTT_TOPIC_STATUS:
        with lock:
            esp32_online = (payload_str.lower() == "true" or payload_str == "1")
        print(f"[STATUS] ESP32 is {'ONLINE' if esp32_online else 'OFFLINE'}")
        return
    
    # Handle Pi control
    if topic == MQTT_TOPIC_PI_CONTROL:
        with lock:
            pi_control_enabled = (payload_str.lower() == "true" or payload_str == "1")
        print(f"[CONTROL] Pi processing {'ENABLED' if pi_control_enabled else 'DISABLED'}")
        return
    
    # Handle data topic
    if topic == MQTT_TOPIC_DATA:
        try:
            payload = json.loads(payload_str)
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
    # IF abnormal_movement == 1 → EMERGENCY OR button == 1 → EMERGENCY
    if btn == 1 or abnormal_movement == 1:
        return "EMERGENCY"
    # ELIF sound_alert == 1 → WARNING
    if sound_alert == 1 or person_present == 0:
        return "WARNING"
    # ELSE → NORMAL
    return "NORMAL"

# ---------------------------
# Actuator control (runs in separate thread)
# ---------------------------
def actuator_control_thread():
    global buzzer_running, current_status
    
    # Ensure actuators are OFF at startup
    GPIO.output(LED_PIN, GPIO.LOW)
    if buzzer_pwm:
        try:
            buzzer_pwm.stop()
        except:
            pass
    buzzer_running = False
    
    # Wait for main loop to be ready (sync with main loop delay)
    print("[ACTUATOR] Waiting 4 seconds for system initialization...")
    time.sleep(4)
    print("[ACTUATOR] Control thread started")
    
    last_status = "NORMAL"
    
    while system_running:
        # Skip actuator control if Pi processing is disabled
        if not pi_control_enabled:
            # Ensure actuators are OFF when disabled
            GPIO.output(LED_PIN, GPIO.LOW)
            if buzzer_running and buzzer_pwm:
                try:
                    buzzer_pwm.stop()
                    buzzer_running = False
                except:
                    pass
            time.sleep(0.5)
            continue
            
        status = current_status
        
        # Only change actuators when status changes
        if status != last_status:
            print(f"[ACTUATOR] Status changed: {last_status} → {status}")
            
            if status == "NORMAL":
                GPIO.output(LED_PIN, GPIO.LOW)
                if buzzer_running and buzzer_pwm:
                    try:
                        buzzer_pwm.stop()
                        buzzer_running = False
                        print("[ACTUATOR] Buzzer OFF (NORMAL)")
                    except Exception as e:
                        print(f"[PWM] Stop error: {e}")
                        buzzer_running = False
            
            elif status == "WARNING":
                GPIO.output(LED_PIN, GPIO.HIGH)
                if buzzer_running and buzzer_pwm:
                    try:
                        buzzer_pwm.stop()
                        buzzer_running = False
                        print("[ACTUATOR] Buzzer OFF (WARNING)")
                    except Exception as e:
                        print(f"[PWM] Stop error: {e}")
                        buzzer_running = False
                    
            elif status == "EMERGENCY":
                GPIO.output(LED_PIN, GPIO.HIGH)
                if not buzzer_running and buzzer_pwm:
                    try:
                        buzzer_pwm.start(75)
                        buzzer_running = True
                        print("[ACTUATOR] Buzzer ON (EMERGENCY)")
                    except Exception as e:
                        print(f"[PWM] Start error: {e}")
            
            last_status = status
        
        time.sleep(0.1)  # Small delay to prevent CPU spinning

# ---------------------------
# Logger (DB)
# ---------------------------
def log_sample(ts, temp, hum, btn, movement_abn, sound, person, status):
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

# ---------------------------
# Main loop
# ---------------------------
def main_loop():
    global current_status, alert_start_time, alert_hold_until, system_running
    print("Starting main loop...")
    print("[MAIN] Waiting 3 seconds before starting main processing...")
    time.sleep(3)  # Wait for all threads to initialize
    print("[MAIN] Main loop active")
    
    # Track performance
    report_interval = 60  # Show report every 60 seconds
    last_report_time = time.time()
    
    # Track Pi status heartbeat
    status_interval = 5  # Send status every 5 seconds
    last_status_time = time.time()
    
    try:
        while system_running:
            # Check if Pi control is enabled
            if not pi_control_enabled:
                print("[CONTROL] Pi processing disabled, waiting...")
                time.sleep(5)
                continue
                
            with lock:
                temp = latest["temperature"]
                hum = latest["humidity"]
                btn = latest["button"]
                movement_abn = latest["abnormal_movement"]
                sound = sound_alert
                person = person_present
                esp32_status = esp32_online

            now = time.time()
            
            # Send periodic status heartbeat
            if now - last_status_time >= status_interval:
                client.publish(MQTT_TOPIC_PI_STATUS, "true", retain=True)
                last_status_time = now
            
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

            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # log to DB
            log_sample(ts, temp, hum, btn, movement_abn, sound, person, status)

            # optional: print short summary
            print(f"{ts} | status={status} | btn={btn} move={movement_abn} person={person} sound={sound} temp={temp} hum={hum}")

            # Show performance report periodically
            if now - last_report_time >= report_interval:
                if detector:
                    print("\n" + "="*60)
                    detector.print_performance_report()
                    print("="*60 + "\n")
                last_report_time = now

            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        # Signal all threads to stop
        system_running = False  # Can use it directly now since declared global above
        print("[GATEWAY] Stopping all threads...")
        
        # Publish Pi offline status
        try:
            client.publish(MQTT_TOPIC_PI_STATUS, "false", retain=True)
            print("[GATEWAY] Published Pi status: offline")
        except:
            pass
        
        # Give threads time to exit gracefully
        time.sleep(0.5)
        
        # Stop PersonDetector and show final report
        if detector:
            detector.stop()
            print("[GATEWAY] PersonDetector stopped")
            print("\n" + "="*60)
            print("FINAL PERFORMANCE REPORT")
            print("="*60)
            detector.print_performance_report()
            print("="*60 + "\n")
        
        # Stop PWM before GPIO cleanup (critical order)
        if buzzer_pwm:
            try:
                if buzzer_running:
                    buzzer_pwm.stop()
                    time.sleep(0.1)  # Give time for PWM to stop
                # Delete PWM object before GPIO cleanup
                buzzer_pwm = None
            except Exception as e:
                print(f"[GATEWAY] PWM cleanup error (ignored): {e}")
        
        # Now cleanup GPIO
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