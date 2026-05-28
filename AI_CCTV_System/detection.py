from ultralytics import YOLO
import torch

class ObjectDetector:
    def __init__(self, model_name='yolov8n.pt'):
        print("Loading YOLO model...")
        self.model = YOLO(model_name)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.interesting_classes = ['person', 'car', 'truck', 'bus', 'bicycle', 'motorcycle']
        self.alert_classes = ['person', 'car', 'truck']
        print("YOLO model loaded!")
    
    def detect(self, frame):
        results = self.model(frame, verbose=False)
        detections = []
        
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    confidence = float(box.conf[0])
                    class_id = int(box.cls[0])
                    class_name = self.model.names[class_id]
                    
                    if class_name in self.interesting_classes:
                        detections.append({
                            'bbox': [int(x1), int(y1), int(x2), int(y2)],
                            'confidence': confidence,
                            'class': class_name,
                            'class_id': class_id,
                            'alert': class_name in self.alert_classes
                        })
        return detections