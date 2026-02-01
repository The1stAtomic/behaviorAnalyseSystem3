import cv2
import time
from datetime import datetime
import os
from ultralytics import YOLO
import torch

model = YOLO(r"yolov8s.pt")
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)

"""
def process_mobile_detection(frame):
    results = model(frame, verbose=False)

    for result in results:
        for box in result.boxes:
            mobile_detected = False

            conf = box.conf[0].item()
            cls = int(box.cls[0].item())
            label = model.names[cls]

            print(f"Detected: {label}, Confidence: {conf:.2f}")

            if conf < 0.8 or label == "phone":
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            display_label = f"{label} ({conf:.2f})"

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(frame, display_label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            mobile_detected = True
    
    return frame, mobile_detected
"""
log_dir = "log"
os.makedirs(log_dir, exist_ok=True)
def process_mobile_detection(frame, save_alerts=False, debug=False):
    """
    Detect phones in frame using YOLO model.
    Returns frame and list of phone bounding boxes in [x1, y1, x2, y2] format.
    
    Args:
        frame: Input frame
        save_alerts: Whether to save detected phones to disk
        debug: Whether to print detected labels for debugging
    """
    results = model(frame, verbose=False)
    phone_boxes = []
    all_detections = []  # For debug output

    for result in results:
        for box in result.boxes:
            conf = box.conf[0].item()
            cls = int(box.cls[0].item())
            label = model.names[cls]
            all_detections.append((label, conf))

            # Lower confidence threshold to 0.5 and check for multiple phone label variants
            if conf < 0.5:
                continue

            # Check for common phone label variations
            if label.lower() in ["cell phone", "phone", "mobile phone", "mobile"]:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                phone_boxes.append([x1, y1, x2, y2])
                
                display_label = f"{label} ({conf:.2f})"
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                cv2.putText(frame, "PHONE DETECTED", (x1, y1 - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                
                if save_alerts:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"log/phone_detected_{timestamp}.jpg"
                    cv2.imwrite(filename, frame)
                    print(f"[ALERT] Capture saved to {filename}")
    
    # Debug output to identify label names
    if debug and all_detections:
        print(f"DEBUG - Detected objects: {all_detections}")

    return frame, phone_boxes

if __name__ == "__main__":
    cap = cv2.VideoCapture(0, cv2.CAP_MSMF)  

    if not cap.isOpened():
        print("Error: Unable to access webcam.")
        exit()

    print("Webcam opened successfully. Starting mobile detection...")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error reading frame.")
            break

        frame, phone_boxes = process_mobile_detection(frame, save_alerts=True)
        mobile_detected = len(phone_boxes) > 0
        cv2.putText(frame, f"Mobile Detected: {mobile_detected}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow("Webcam with Detection", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Detection ended. Closing webcam.")
            break

    cap.release()  
    cv2.destroyAllWindows()  


