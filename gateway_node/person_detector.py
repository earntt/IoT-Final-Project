import cv2
import threading
import time
from ultralytics import YOLO

class PersonDetector:
    def __init__(self, model_path='yolo11n.pt'):
        """
        โหลดโมเดลเตรียมไว้
        """
        print(f"[VISION] Loading YOLO model ({model_path})...")
        self.model = YOLO(model_path)
        
        # ตัวแปรสำหรับ Runtime จริง
        self.running = False
        self.person_detected = 0 
        self.thread = None
        self.cap = None

    def detect_frame(self, frame, draw=False):
        """
        ฟังก์ชันหลัก: รับภาพ -> คืนค่า (เจอคนไหม?, ภาพที่วาดกรอบแล้ว)
        ใช้ได้ทั้งโหมด Debug และโหมดใช้งานจริง
        """
        # Run YOLO (conf=0.5, detect person class only)
        results = self.model(frame, verbose=False, conf=0.5, classes=[0])
        
        person_count = 0
        annotated_frame = frame
        
        for r in results:
            person_count = len(r.boxes)
            if draw and person_count > 0:
                annotated_frame = r.plot()
        return person_count, annotated_frame

    # ---------------------------------------------------------
    # ส่วนสำหรับใช้งานจริงกับ Gateway (Run in Thread)
    # ---------------------------------------------------------
    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._process_thread)
        self.thread.daemon = True
        self.thread.start()
        print("[VISION] Background thread started.")

    def stop(self):
        self.running = False
        if self.thread: self.thread.join()
        if self.cap: self.cap.release()
        
    def _process_thread(self):
        """Loop ทำงานเบื้องหลัง (ไม่แสดงภาพ เพื่อประหยัด Resource)"""
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, 640)
        self.cap.set(4, 480)
        
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(1)
                continue
            
            # เรียกใช้ Logic ตรวจจับ (ไม่วาดภาพ)
            found, _ = self.detect_frame(frame, draw=False)
            self.person_detected = found
            
            # (Optional) ถ้าอยากดูภาพตอนรัน Gateway จริง ให้แก้ draw=True และใส่ cv2.imshow ตรงนี้ได้
            # แต่ต้องระวังเรื่อง Thread GUI

# ---------------------------------------------------------
# ส่วนสำหรับ Debug (Run as Main)
# ---------------------------------------------------------
if __name__ == "__main__":
    print("--- DEBUG MODE (Running in Main Thread) ---")
    print("Press 'q' to exit")

    # 1. สร้าง Object
    detector = PersonDetector(model_path='yolo11n.pt') 

    # 2. เปิดกล้องเอง (ใน Main Thread)
    cap = cv2.VideoCapture(0)
    cap.set(3, 640)
    cap.set(4, 480)

    if not cap.isOpened():
        print("Error: Could not open camera.")
        exit()

    try:
        while True:
            ret, frame = cap.read()
            if not ret: break

            # 3. เรียกใช้ฟังก์ชัน detect และสั่งให้วาดภาพ (draw=True)
            person_count, output_frame = detector.detect_frame(frame, draw=True)

            # 4. แสดงผล (ทำงานได้แน่นอนเพราะอยู่ใน Main Thread)
            status_text = str(person_count) + " PERSON"
            color = (0, 0, 255) if person_count > 0 else (0, 255, 0)
            
            cv2.putText(output_frame, status_text, (20, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            
            cv2.imshow("Debug Vision", output_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Debug Stopped.")