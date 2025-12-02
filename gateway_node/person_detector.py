import cv2
import threading
import time
import psutil
from ultralytics import YOLO

class PersonDetector:
    def __init__(self, model_path='yolov11n.pt'):
        print(f"[VISION] Loading YOLO model ({model_path})...")
        self.model = YOLO(model_path)
        
        self.running = False
        self.person_detected = 0 
        self.thread = None
        self.cap = None

        # --- เก็บสถิติ ---
        self.stats = {
            "start_time": None,
            "total_frames": 0,
            "total_inference_time_ms": 0,
            "max_inference_ms": 0,
            "min_inference_ms": 9999,
        }

    def reset_stats(self):
        self.stats = {
            "start_time": time.time(),
            "total_frames": 0,
            "total_inference_time_ms": 0,
            "max_inference_ms": 0,
            "min_inference_ms": 9999,
        }

    def detect_frame(self, frame, draw=False):
        # เริ่มจับเวลา Model Inference (เฉพาะตอน AI คิด)
        inference_start = time.time()
        
        # Run YOLO
        results = self.model(frame, verbose=False, conf=0.5, classes=[0])
        
        inference_end = time.time()
        
        # คำนวณ Inference Time (ms)
        inference_ms = (inference_end - inference_start) * 1000
        
        person_count = 0
        annotated_frame = frame
        
        for r in results:
            person_count = len(r.boxes)
            if draw and person_count > 0:
                annotated_frame = r.plot()
        
        # --- บันทึกสถิติ ---
        self.stats["total_frames"] += 1
        self.stats["total_inference_time_ms"] += inference_ms
        
        if inference_ms > self.stats["max_inference_ms"]: self.stats["max_inference_ms"] = inference_ms
        if inference_ms < self.stats["min_inference_ms"]: self.stats["min_inference_ms"] = inference_ms

        return person_count, annotated_frame

    def print_performance_report(self):
        """ แสดงรายงานเฉพาะ Model Performance & Resource Usage """
        duration = time.time() - self.stats["start_time"]
        total_frames = self.stats["total_frames"]
        
        if total_frames == 0: return

        # คำนวณค่าเฉลี่ย
        avg_fps = total_frames / duration
        avg_inference = self.stats["total_inference_time_ms"] / total_frames
        
        # อ่านค่า Hardware
        cpu_usage = psutil.cpu_percent()
        ram_usage = psutil.virtual_memory().percent

        print("\n" + "="*60)
        print("📊  PERFORMANCE REPORT (ผลการทดสอบประสิทธิภาพ)")
        print("="*60)
        
        print(f"1. MODEL PERFORMANCE (โมเดล YOLO)")
        print(f"   - Average FPS:           {avg_fps:.2f} frames/sec")
        print(f"   - Inference Time (Avg):  {avg_inference:.2f} ms")
        print(f"   - Inference Time (Max):  {self.stats['max_inference_ms']:.2f} ms")
        print(f"   - Inference Time (Min):  {self.stats['min_inference_ms']:.2f} ms")
        
        print(f"\n2. RESOURCE USAGE (ทรัพยากรเครื่อง)")
        print(f"   - CPU Usage:             {cpu_usage}%")
        print(f"   - RAM Usage:             {ram_usage}%")
        print("="*60 + "\n")

    # --- Standard Methods ---
    def start(self):
        if self.running: return
        self.running = True
        self.reset_stats()
        self.thread = threading.Thread(target=self._process_thread)
        self.thread.daemon = True
        self.thread.start()
        print("[VISION] Started.")

    def stop(self):
        self.running = False
        if self.thread: self.thread.join()
        if self.cap:
            try:
                self.cap.stop()  # For Picamera2
            except AttributeError:
                try:
                    self.cap.release()  # For cv2.VideoCapture
                except:
                    pass
        self.print_performance_report() # <--- สรุปผลตอนจบ
        print("[VISION] Stopped.")

    def _process_thread(self):
        """Loop ทำงานเบื้องหลัง (ไม่แสดงภาพ เพื่อประหยัด Resource)"""
        # Use Picamera2 for Raspberry Pi Camera
        use_picamera = False
        try:
            from picamera2 import Picamera2
            self.cap = Picamera2()
            config = self.cap.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
            self.cap.configure(config)
            self.cap.start()
            use_picamera = True
            print("[VISION] Using Picamera2")
        except (ImportError, IndexError, RuntimeError) as e:
            print(f"[VISION] Picamera2 not available ({e}), falling back to cv2.VideoCapture")
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                print("[VISION] ERROR: Cannot open camera with cv2.VideoCapture either!")
                return
            self.cap.set(3, 640)
            self.cap.set(4, 480)
            use_picamera = False
        
        while self.running:
            if use_picamera:
                frame = self.cap.capture_array()
            else:
                ret, frame = self.cap.read()
                if not ret:
                    time.sleep(0.01)
                    continue
            count, _ = self.detect_frame(frame, draw=False)
            self.person_detected = count

# --- Debug Mode ---
if __name__ == "__main__":
    print("Running Debug Mode... Press 'q' to stop.")
    detector = PersonDetector(model_path='yolo11n.pt') 

    # Initialize camera (try Picamera2 first, fallback to cv2.VideoCapture)
    use_picamera = False
    try:
        from picamera2 import Picamera2
        cap = Picamera2()
        config = cap.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
        cap.configure(config)
        cap.start()
        use_picamera = True
        print("Using Picamera2")
    except (ImportError, IndexError, RuntimeError) as e:
        print(f"Picamera2 not available ({e}), using cv2.VideoCapture")
        cap = cv2.VideoCapture(0)
        cap.set(3, 640)
        cap.set(4, 480)
        use_picamera = False
        
        if not cap.isOpened():
            print("Error: Could not open camera.")
            exit()

    detector.reset_stats()

    try:
        while True:
            # Capture frame
            if use_picamera:
                frame = cap.capture_array()
            else:
                ret, frame = cap.read()
                if not ret: 
                    print("Error: Failed to capture frame")
                    break

            # Detect and draw
            person_count, output_frame = detector.detect_frame(frame, draw=True)
            
            # Display result
            status_text = f"Count: {person_count} PERSON(S)"
            color = (0, 0, 255) if person_count > 0 else (0, 255, 0)
            cv2.putText(output_frame, status_text, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            cv2.imshow("Debug Vision", output_frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except KeyboardInterrupt:
        pass
    finally:
        if use_picamera:
            cap.stop()
        else:
            cap.release()
        cv2.destroyAllWindows()
        detector.print_performance_report()