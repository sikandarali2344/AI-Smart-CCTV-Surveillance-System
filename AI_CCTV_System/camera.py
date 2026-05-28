import cv2
import numpy as np
from detection import ObjectDetector
import threading

class VideoCamera:
    def __init__(self, source=0):
        self.cap = cv2.VideoCapture(source)
        self.detector = ObjectDetector()
        self.current_frame = None
        self.lock = threading.Lock()
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        self.thread = threading.Thread(target=self.update_frames)
        self.thread.daemon = True
        self.thread.start()
    
    def update_frames(self):
        while True:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.current_frame = frame
    
    def get_frame(self):
        with self.lock:
            if self.current_frame is None:
                return None, []
            frame = self.current_frame.copy()
        
        detections = self.detector.detect(frame)
        
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            label = f"{det['class']} ({det['confidence']:.2f})"
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            cv2.rectangle(frame, (x1, y1 - 20), (x1 + label_size[0], y1), (0, 255, 0), -1)
            cv2.putText(frame, label, (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        
        return frame, detections
    
    def get_current_frame(self):
        with self.lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
        return None
    
    def __del__(self):
        self.cap.release()