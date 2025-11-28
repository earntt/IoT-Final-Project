import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
import time
import json
import queue
from queue import Queue

# ======================= CONFIGURATION =======================
# --- Ubidots Configuration ---
UBIDOTS_TOKEN = "BBUS-l5K2cckgSINlQm6LJrwiDyf6JCXtpk"
UBIDOTS_DEVICE_LABEL = "raspberrypi"
UBIDOTS_BROKER = "industrial.api.ubidots.com"
UBIDOTS_PORT = 1883

# --- Local MQTT Broker Configuration (สำหรับรับข้อมูลจาก ESP32) ---
LOCAL_BROKER = "localhost"
LOCAL_PORT = 1883

# --- GPIO Pins ---
LED_PIN = 17
BUZZER_PIN = 27

FREQUENCY = 1000

# --- Alert Settings ---
ALERT_DURATION_SECONDS = 5

# ======================= INITIALIZATION =======================
# --- Initialize GPIO ---
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)

pwm = GPIO.PWM(BUZZER_PIN, FREQUENCY)

# --- สร้าง Queue เพื่อเป็นตัวกลางสื่อสารระหว่าง Threads ---
data_queue = Queue()

# --- ตัวแปรสำหรับจัดการสถานะ Alert แบบ Non-Blocking ---
alert_active = False
alert_start_time = 0

# --- เก็บสถานะล่าสุดของแต่ละ topic เพื่อป้องกันการส่งซ้ำโดยไม่จำเป็น ---
latest_data = {
    "temperature": None,
    "humidity": None,
    "heart_rate": None,
    "button": 0,
    "abnormal_movement": 0
}
# --- เก็บค่าที่ส่งล่าสุดไป Ubidots ---
last_sent = {
    "temperature": None,
    "humidity": None,
    "heart_rate": None
}
# --- สำหรับจำเวลาที่ส่ง alert ล่าสุด แยกปุ่มและ movement ---
button_alert_active = False
button_alert_hold_until = 0
movement_alert_active = False
movement_alert_hold_until = 0

# ======================= MQTT CALLBACKS =======================

def on_local_connect(client, userdata, flags, rc):
    """Callback เมื่อเชื่อมต่อ Local Broker (รับข้อมูลจาก ESP32) สำเร็จ"""
    if rc == 0:
        # Subscribe ทุก topic
        client.subscribe("esp32/temperature")
        client.subscribe("esp32/humidity")
        client.subscribe("esp32/heart_rate")
        client.subscribe("esp32/button")
        client.subscribe("esp32/abnormal_movement")
        print("Connected to LOCAL MQTT Broker successfully!")
    else:
        print(f"Failed to connect to LOCAL Broker, return code {rc}")

def on_local_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    if topic == "esp32/temperature":
        latest_data["temperature"] = float(payload)
    elif topic == "esp32/humidity":
        latest_data["humidity"] = float(payload)
    elif topic == "esp32/heart_rate":
        latest_data["heart_rate"] = float(payload)
    elif topic == "esp32/button":
        latest_data["button"] = int(payload)
    elif topic == "esp32/abnormal_movement":
        latest_data["abnormal_movement"] = int(payload)

# ======================= MAIN PROGRAM EXECUTION =======================

# --- ตั้งค่า Local MQTT Client (สำหรับรับข้อมูล) ---
local_client = mqtt.Client(client_id="Pi_Gateway_Subscriber")
local_client.on_connect = on_local_connect
local_client.on_message = on_local_message
local_client.connect("localhost", 1883, 60)
local_client.loop_start()

# --- ตั้งค่า Ubidots MQTT Client (สำหรับส่งข้อมูล) ---
ubidots_client = mqtt.Client(client_id="Pi_Gateway_Publisher")
ubidots_client.username_pw_set(UBIDOTS_TOKEN, password="")

ALERT_DURATION_SECONDS = 5
alert_active = False
alert_start_time = 0

# --- เชื่อมต่อกับ Brokers ---
try:
    print("Connecting to LOCAL Broker...")
    local_client.connect(LOCAL_BROKER, LOCAL_PORT, 60)
    local_client.loop_start()  # รันใน background thread

    print("Connecting to UBIDOTS Broker...")
    ubidots_client.connect(UBIDOTS_BROKER, UBIDOTS_PORT, 60)
    ubidots_client.loop_start() # รันใน background thread

except Exception as e:
    print(f"FATAL: Could not connect to a broker. Error: {e}")
    exit()

print("\nSystem Gateway Started. Waiting for data from ESP32...")
print("Press Ctrl+C to exit.")

try:
    while True:
        # --- Publish sensor data เฉพาะเมื่อค่ามีการเปลี่ยนแปลง ---
        if latest_data["temperature"] is not None and latest_data["temperature"] != last_sent["temperature"]:
            topic = f"/v1.6/devices/{UBIDOTS_DEVICE_LABEL}/temperature"
            ubidots_client.publish(topic, str(latest_data["temperature"]))
            last_sent["temperature"] = latest_data["temperature"]
        if latest_data["humidity"] is not None and latest_data["humidity"] != last_sent["humidity"]:
            topic = f"/v1.6/devices/{UBIDOTS_DEVICE_LABEL}/humidity"
            ubidots_client.publish(topic, str(latest_data["humidity"]))
            last_sent["humidity"] = latest_data["humidity"]
        if latest_data["heart_rate"] is not None and latest_data["heart_rate"] != last_sent["heart_rate"]:
            topic = f"/v1.6/devices/{UBIDOTS_DEVICE_LABEL}/heart-rate"
            ubidots_client.publish(topic, str(latest_data["heart_rate"]))
            last_sent["heart_rate"] = latest_data["heart_rate"]

        now = time.time()
        # --- กรณีปุ่มกด ---
        if latest_data["button"] == 1 and not button_alert_active:
            print("BUTTON ALERT! LED/BUZZER ON, send 1 to Ubidots (button-pressed)")
            button_alert_active = True
            button_alert_hold_until = now + ALERT_DURATION_SECONDS
            GPIO.output(LED_PIN, GPIO.HIGH)
            pwm.start(80)
            topic_btn = f"/v1.6/devices/{UBIDOTS_DEVICE_LABEL}/button-pressed"
            ubidots_client.publish(topic_btn, "1")
        if button_alert_active and now < button_alert_hold_until:
            topic_btn = f"/v1.6/devices/{UBIDOTS_DEVICE_LABEL}/button-pressed"
            ubidots_client.publish(topic_btn, "1")
        if button_alert_active and now >= button_alert_hold_until:
            print("Button alert finished. LED/BUZZER OFF, send 0 to Ubidots (button-pressed)")
            GPIO.output(LED_PIN, GPIO.LOW)
            pwm.stop()
            topic_btn = f"/v1.6/devices/{UBIDOTS_DEVICE_LABEL}/button-pressed"
            ubidots_client.publish(topic_btn, "0")
            button_alert_active = False

        # --- กรณี movement ผิดปกติ ---
        if latest_data["abnormal_movement"] == 1 and not movement_alert_active:
            print("MOVEMENT ALERT! LED/BUZZER ON, send 1 to Ubidots (movement)")
            movement_alert_active = True
            movement_alert_hold_until = now + ALERT_DURATION_SECONDS
            GPIO.output(LED_PIN, GPIO.HIGH)
            pwm.start(80)
            topic_abn = f"/v1.6/devices/{UBIDOTS_DEVICE_LABEL}/movement"
            ubidots_client.publish(topic_abn, "1")
        if movement_alert_active and now < movement_alert_hold_until:
            topic_abn = f"/v1.6/devices/{UBIDOTS_DEVICE_LABEL}/movement"
            ubidots_client.publish(topic_abn, "1")
        if movement_alert_active and now >= movement_alert_hold_until:
            print("Movement alert finished. LED/BUZZER OFF, send 0 to Ubidots (movement)")
            GPIO.output(LED_PIN, GPIO.LOW)
            pwm.stop()
            topic_abn = f"/v1.6/devices/{UBIDOTS_DEVICE_LABEL}/movement"
            ubidots_client.publish(topic_abn, "0")
            movement_alert_active = False

        time.sleep(0.2)
except KeyboardInterrupt:
    print("\nScript terminated by user.")
finally:
    local_client.loop_stop()
    ubidots_client.loop_stop()
    GPIO.cleanup()
    print("System shut down cleanly.")