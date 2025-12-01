import cv2
import threading
import time
import psutil
from ultralytics import YOLO

class PersonDetector:
    def __init__(self, model_path='yolo11n.pt'):
        print(f"[VISION] Loading YOLO model ({model_path})...")
        self.model = YOLO(model_path)

        self.running = False
        self.person_detected = 0 
        self.thread = None
        self.cap = None

        # --- ส่วน Performance & Latency ---
        self.stats = {
            "start_time": None,
            "total_frames": 0,
            "total_inference_time_ms": 0,  # เวลาที่ YOLO ใช้ประมวลผล (Inference)
            "total_process_time_ms": 0,    # เวลาตั้งแต่รับภาพจนวาดเสร็จ (System Latency)
            "max_inference_ms": 0,
            "min_inference_ms": 9999,
        }

    def reset_stats(self):
        self.stats = {
            "start_time": time.time(),
            "total_frames": 0,
            "total_inference_time_ms": 0,
            "total_process_time_ms": 0,
            "max_inference_ms": 0,
            "min_inference_ms": 9999,
        }

    def detect_frame(self, frame, draw=False):
        # เริ่มจับเวลา System Latency (Processing)
        process_start = time.time()
        
        # เริ่มจับเวลา Model Inference
        inference_start = time.time()
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
        
        # จบจับเวลา System Latency
        process_end = time.time()
        process_ms = (process_end - process_start) * 1000

        # --- บันทึกสถิติ ---
        self.stats["total_frames"] += 1
        self.stats["total_inference_time_ms"] += inference_ms
        self.stats["total_process_time_ms"] += process_ms
        
        if inference_ms > self.stats["max_inference_ms"]: self.stats["max_inference_ms"] = inference_ms
        if inference_ms < self.stats["min_inference_ms"]: self.stats["min_inference_ms"] = inference_ms

        return person_count, annotated_frame

    def print_performance_report(self):
        """ แสดงรายงาน Model Performance & Latency """
        duration = time.time() - self.stats["start_time"]
        total_frames = self.stats["total_frames"]
        
        if total_frames == 0: return

        # คำนวณค่าเฉลี่ย
        avg_fps = total_frames / duration
        avg_inference = self.stats["total_inference_time_ms"] / total_frames
        avg_latency = self.stats["total_process_time_ms"] / total_frames
        
        # อ่านค่า Hardware
        cpu_usage = psutil.cpu_percent()
        ram_usage = psutil.virtual_memory().percent

        print("\n" + "="*60)
        print("PERFORMANCE & LATENCY REPORT")
        print("="*60)
        
        print(f"1. MODEL PERFORMANCE (ประสิทธิภาพโมเดล)")
        print(f"   - Average FPS:           {avg_fps:.2f} frames/sec")
        print(f"   - Inference Time (Avg):  {avg_inference:.2f} ms (เวลาที่ AI ใช้คิด)")
        print(f"   - Inference Time (Max):  {self.stats['max_inference_ms']:.2f} ms")
        print(f"   - Inference Time (Min):  {self.stats['min_inference_ms']:.2f} ms")
        
        print(f"\n2. SYSTEM LATENCY (ความหน่วงระบบ)")
        print(f"   - Processing Latency:    {avg_latency:.2f} ms (รวมวาดภาพ+Logic)")
        print(f"   - End-to-End Delay:      ~{avg_latency + 10:.2f} ms (ประมาณการรวมกล้อง)")

        print(f"\n3. RESOURCE USAGE (ทรัพยากรเครื่อง)")
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
        if self.cap: self.cap.release()
        self.print_performance_report()
        print("[VISION] Stopped.")

    def _process_thread(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, 640)
        self.cap.set(4, 480)
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            count, _ = self.detect_frame(frame, draw=False)
            self.person_detected = count

# --- Debug Mode ---
if __name__ == "__main__":
    print("Running Debug Mode... Press 'q' to stop.")
    detector = PersonDetector(model_path='yolo11n.pt') # หรือ yolov8n.pt
    detector.reset_stats()
    
    cap = cv2.VideoCapture(0)
    cap.set(3, 640)
    cap.set(4, 480)

    try:
        while True:
            ret, frame = cap.read()
            if not ret: break
            
            # เรียกใช้และเก็บสถิติ
            count, out = detector.detect_frame(frame, draw=True)
            
            cv2.putText(out, f"Count: {count}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
            cv2.imshow("Debug", out)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        detector.print_performance_report()