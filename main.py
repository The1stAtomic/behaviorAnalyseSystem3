import time
import cv2
import numpy as np
from ultralytics import YOLO
import yaml
from pathlib import Path
from detection.phone_detector.phone import process_mobile_detection
from tracking.tracker import PlayerTracker
from detection.head_pose_estimation.face_detection import FaceDetector
from detection.head_pose_estimation.mark_detection import MarkDetector
from detection.head_pose_estimation.pose_estimation import PoseEstimator
from detection.head_pose_estimation.utils import refine
from signals.frame_signal_builder import FrameSignalBuilder
from signals.temporal_aggregator import TemporalAggregationPipeline
from signals.session_logger import SessionLogger
from signals.visual_overlay import VisualOverlay
from signals.api_handler import APIHandler
from memory.feature_buffer import FeatureBuffer
from inference.behavior_rules import BehaviorRuleEngine
import os
from detection.face_recognition.insight_recognizer import InsightFaceRecognizer

def _cv2_imshow_available() -> bool:
  """Check if cv2.imshow is available in this environment."""
  try:
    test_img = np.zeros((10, 10, 3), dtype=np.uint8)
    cv2.imshow("_cv2_test", test_img)
    cv2.waitKey(1)
    cv2.destroyWindow("_cv2_test")
    return True
  except Exception:
    return False
def load_config():
    config_path = Path("config/settings.yaml")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path.absolute()}")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        if config is None:
            raise ValueError(f"Config file is empty or invalid: {config_path.absolute()}")
        return config

#Head pose estimation

def estimate_head_direction(student_crop, face_detector, mark_detector, pose_estimator):
  """
    Estimate head direction using head pose estimation.
    Returns direction string based on rotation angles.
  """
  if student_crop.size == 0:
    return "unknown"
  
  crop_h, crop_w = student_crop.shape[:2]
  if crop_h < 20 or crop_w < 20:
    return "unknown"
  
  # Step 1: Detect faces in the crop
  faces, _ = face_detector.detect(student_crop, 0.7)
  
  if len(faces) == 0:
    return "no_face"
  
  # Step 2: Get facial landmarks for the first face
  face = refine(faces, crop_w, crop_h, 0.15)[0]
  x1, y1, x2, y2 = face[:4].astype(int)
  
  # Ensure coordinates are within bounds
  x1, y1 = max(0, x1), max(0, y1)
  x2, y2 = min(crop_w, x2), min(crop_h, y2)
  
  if x2 <= x1 or y2 <= y1:
    return "unknown"
  
  patch = student_crop[y1:y2, x1:x2]
  if patch.size == 0:
    return "unknown"
  
  # Step 3: Detect landmarks
  marks = mark_detector.detect([patch])[0].reshape([68, 2])
  
  # Convert to global coordinates
  marks *= (x2 - x1)
  marks[:, 0] += x1
  marks[:, 1] += y1
  
  # Step 4: Estimate pose
  rotation_vector, _ = pose_estimator.solve(marks)
  
  # Convert rotation vector to Euler angles
  rotation_mat, _ = cv2.Rodrigues(rotation_vector)
  pose_mat = cv2.hconcat((rotation_mat, np.zeros((3, 1))))
  _, _, _, _, _, _, euler_angles = cv2.decomposeProjectionMatrix(pose_mat)
  
  pitch, yaw, roll = euler_angles.flatten()[:3]
  
  # Determine direction based on angles
  # Yaw: left-right, Pitch: up-down
  if abs(pitch) > 15:  # Looking up or down
    if pitch > 15:
      return "down"
    else:
      return "up"
  elif abs(yaw) > 15:  # Looking left or right
    if yaw > 15:
      return "right"
    else:
      return "left"
  else:
    return "forward"
  
  return "unknown"

def iou(boxA, boxB):
    """
    Compute Intersection over Union between two boxes.
    Boxes: [x1, y1, x2, y2]
    """
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interW = max(0, xB - xA)
    interH = max(0, yB - yA)
    interArea = interW * interH

    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    if boxAArea + boxBArea - interArea == 0:
        return 0.0

    return interArea / (boxAArea + boxBArea - interArea)

def intersection_over_phone(box_student, box_phone):
    """Intersection area divided by phone box area. Boxes: [x1,y1,x2,y2]."""
    xA = max(box_student[0], box_phone[0])
    yA = max(box_student[1], box_phone[1])
    xB = min(box_student[2], box_phone[2])
    yB = min(box_student[3], box_phone[3])

    interW = max(0, xB - xA)
    interH = max(0, yB - yA)
    interArea = interW * interH
    phoneArea = max(0, (box_phone[2] - box_phone[0]) * (box_phone[3] - box_phone[1]))
    if phoneArea == 0:
      return 0.0
    return interArea / phoneArea

def phone_center_inside(student_box, phone_box):
    """Check if the phone box center lies inside the student's box."""
    cx = (phone_box[0] + phone_box[2]) / 2.0
    cy = (phone_box[1] + phone_box[3]) / 2.0
    return (student_box[0] <= cx <= student_box[2]) and (student_box[1] <= cy <= student_box[3])
  
#Main

def main():
  config = load_config()
  
  camera_index = config["camera"]["index"]
  frame_sample_rate = config["video"]["frame_sample_rate"]
  iou_threshold = config["fusion"]["iou_threshold"]
  phone_overlap_mode = config["fusion"].get("phone_overlap_mode", "ratio")
  phone_overlap_threshold = float(config["fusion"].get("phone_overlap_threshold", 0.5))
  min_confidence = config["detection"].get("min_confidence", 0.25)
  nms_iou = config["detection"].get("nms_iou", 0.5)
  min_area_ratio = config["detection"].get("min_area_ratio", 0.0)
  
  # Initialize tracker with re-ID capability
  tracker = PlayerTracker(model_path=config["detection"]["model"])
  tracker.model.conf = min_confidence  # Set confidence threshold
  tracker.similarity_threshold = config.get("tracking", {}).get("similarity_threshold", 0.8)
  tracker.max_distance_threshold = config.get("tracking", {}).get("max_distance_threshold", 100)
  
  # Initialize head pose estimation components
  head_pose_dir = os.path.join(os.path.dirname(__file__), "detection", "head_pose_estimation")
  face_detector = FaceDetector(os.path.join(head_pose_dir, "assets", "face_detector.onnx"))
  mark_detector = MarkDetector(os.path.join(head_pose_dir, "assets", "face_landmarks.onnx"))
  # Use dummy dimensions, will be updated per crop
  pose_estimator = PoseEstimator(640, 480)
  
  # Initialize signal builder
  signal_builder = FrameSignalBuilder()
  
  # Initialize feature buffer with 20-second sliding window (faster phone detection)
  feature_buffer = FeatureBuffer(window_size=20.0)
  
  # Initialize temporal aggregator for behavioral metrics
  aggregation_pipeline = TemporalAggregationPipeline()
  
  # Track last API metric send time per student (send immediately on detection, then every 5 minutes)
  last_api_metric_send_per_student = {}  # track_id -> timestamp of last API send
  api_metric_interval = 300.0  # Send metrics every 5 minutes per student
  
  # Initialize rule-based inference engine
  rule_engine = BehaviorRuleEngine(config={
    "attention_threshold": 0.5,
    "phone_risk_threshold": 0.4,
    "engagement_risk_threshold": 0.6,
    "min_samples_for_alert": 5
  })
  
  # Initialize session logger for output
  session_logger = SessionLogger(session_name=None, output_dir="log")
  
  # Initialize API handler
  try:
    db_config = config.get("database", {}).get("api", {})
    api_url = db_config.get("url", "https://attcam.cc/api/logs")
    timeout = db_config.get("timeout", 10)
    db_handler = APIHandler(
        api_url=api_url,
        timeout=timeout
    )
    db_enabled = True
  except Exception as e:
    print(f"⚠ Warning: Could not initialize API handler: {e}")
    print("  Continuing without remote logging...")
    db_handler = None
    db_enabled = False
  
  # Initialize visual overlay for real-time feedback
  visual_overlay = VisualOverlay()
  show_window = bool(config['debug'].get('show_window', True))
  if show_window and not _cv2_imshow_available():
    print("⚠ Warning: OpenCV GUI not available. Disabling window display.")
    show_window = False

  # Initialize face recognizer (InsightFace)
  face_rec_cfg = config.get("face_recognition", {})
  recognizer = None
  if face_rec_cfg.get("enabled", False):
    try:
      recognizer = InsightFaceRecognizer(
        known_faces_dir=face_rec_cfg.get("known_faces_dir", "know_faces"),
        det_size=tuple(face_rec_cfg.get("det_size", [640, 640])),
        provider=face_rec_cfg.get("provider", "cpu"),
        similarity_threshold=float(face_rec_cfg.get("similarity_threshold", 0.35)),
        min_face_size=int(face_rec_cfg.get("min_face_size", 40)),
      )
      print("Face recognizer initialized.")
    except Exception as e:
      print(f"⚠ Warning: Face recognition disabled due to error: {e}")
      recognizer = None
  
  # Insert session into database
  if db_enabled:
    db_handler.insert_session(session_logger.session_name)
  
  cap = cv2.VideoCapture(camera_index)
  if not cap.isOpened():
      print("Error: Could not open video.")
      return
    
  frame_count = 0
  start_time = time.time()
  
  # FPS tracking
  fps_start_time = time.time()
  fps_frame_count = 0
  current_fps = 0.0
  
  # Track unique students
  students_tracked = set()
  students_logged_to_db = set()  # Track which students we've inserted into students table
  last_attendance_time = {}  # Track last attendance check-in time for each student
  ATTENDANCE_INTERVAL = 300  # 5 minutes in seconds
  
  # Track phone detection per student for direct metrics
  student_phone_risk = {}  # track_id -> current phone risk (0.0-1.0)
  
  while True:
    ret, frame = cap.read()
    if not ret:
        print("Error: Could not read frame.")
        break
      
    frame_count += 1
    if frame_count % frame_sample_rate != 0:
        continue
    
    # Calculate FPS
    fps_frame_count += 1
    if fps_frame_count >= 30:
      fps_elapsed = time.time() - fps_start_time
      current_fps = fps_frame_count / fps_elapsed if fps_elapsed > 0 else 0
      fps_start_time = time.time()
      fps_frame_count = 0
      
    timestamp = time.time() - start_time
    
    #Step 3-4: Detection and Tracking with Re-ID
    # Detect persons in current frame
    detections = tracker.detect_players(frame)
    
    # Assign player IDs with re-identification
    tracked_players = tracker.assign_player_ids(frame, detections, frame_count)
    
    if not tracked_players:
        continue
    
    # Apply area filtering to remove tiny/sliver boxes
    frame_h, frame_w = frame.shape[:2]
    min_area_px = min_area_ratio * frame_h * frame_w
    filtered = []
    for player_id, bbox, conf in tracked_players:
      x1, y1, x2, y2 = bbox
      area = max(0, x2 - x1) * max(0, y2 - y1)
      if area < min_area_px:
        continue
      filtered.append((player_id, bbox, conf))

    if not filtered:
        continue
    
    #Step 5: Head Direction Estimation
    students = []
    for player_id, bbox, conf in filtered:
      # Track unique students
      students_tracked.add(player_id)
      
      # Insert into students table when first seen
      if db_enabled and player_id not in students_logged_to_db:
        db_handler.insert_or_update_student(session_logger.session_name, player_id)
        db_handler.check_in_student(session_logger.session_name, player_id)
        students_logged_to_db.add(player_id)
        last_attendance_time[player_id] = timestamp
        # Initialize to 0 so metrics are sent immediately on first aggregation
        last_api_metric_send_per_student[player_id] = 0.0
      
      # Check if 5 minutes have passed since last attendance record
      if db_enabled and player_id in last_attendance_time:
        time_since_last = timestamp - last_attendance_time[player_id]
        if time_since_last >= ATTENDANCE_INTERVAL:
          db_handler.check_in_student(session_logger.session_name, player_id)
          last_attendance_time[player_id] = timestamp
          print(f"✓ Periodic attendance recorded for Student #{player_id} ({time_since_last/60:.1f} min)")
      
      x1, y1, x2, y2 = map(int, bbox)
      student_crop = frame[y1:y2, x1:x2]
      
      # Update pose estimator dimensions for this crop
      if student_crop.size > 0:
        crop_h, crop_w = student_crop.shape[:2]
        pose_estimator.size = (crop_h, crop_w)
        pose_estimator.focal_length = crop_w
        pose_estimator.camera_center = (crop_w / 2, crop_h / 2)
        pose_estimator.camera_matrix = np.array(
          [[pose_estimator.focal_length, 0, pose_estimator.camera_center[0]],
           [0, pose_estimator.focal_length, pose_estimator.camera_center[1]],
           [0, 0, 1]], dtype="double")
      
      head_dir = estimate_head_direction(student_crop, face_detector, mark_detector, pose_estimator)

      # Face recognition
      identity_name = None
      identity_score = None
      if recognizer is not None:
        try:
          identity_name, identity_score = recognizer.recognize(student_crop)
        except Exception as _:
          identity_name, identity_score = None, None
      
      students.append({
        "track_id": player_id,
        "bbox": bbox,
        "head_direction": head_dir,
        "confidence": float(conf),
        "identity_name": identity_name,
        "identity_score": float(identity_score) if identity_score is not None else None
      })
      
    #Step 6: Phone detection
    _, phone_boxes = process_mobile_detection(frame, debug=False)
    
    #Step 7: Signal fusion (phone association)
    for student in students:
      has_phone = False
      for phone_box in phone_boxes:
        if phone_overlap_mode == "iou":
          if iou(student["bbox"], phone_box) > iou_threshold:
            has_phone = True
            break
        elif phone_overlap_mode == "ratio":
          # Intersection relative to phone area (handles small phones in large person boxes)
          if intersection_over_phone(student["bbox"], phone_box) >= phone_overlap_threshold:
            has_phone = True
            break
        elif phone_overlap_mode == "center":
          if phone_center_inside(student["bbox"], phone_box):
            has_phone = True
            break
        else:
          # default to ratio if unknown mode
          if intersection_over_phone(student["bbox"], phone_box) >= phone_overlap_threshold:
            has_phone = True
            break

      student["phone_detected"] = has_phone
      
      # Update phone risk directly from detection (not from feature buffer)
      if has_phone:
        # Phone detected: risk jumps to 1.0
        student_phone_risk[student["track_id"]] = 1.0
      else:
        # No phone: decay risk slowly (15% decay per frame)
        current_risk = student_phone_risk.get(student["track_id"], 0.0)
        student_phone_risk[student["track_id"]] = current_risk * 0.85
    
    #Step 8: Build frame signal
    frame_signal = signal_builder.build(
        frame_id=frame_count,
        timestamp=timestamp,
        tracked_students=students
    )
    
    # Log frame data
    session_logger.log_frame_data(frame_count, timestamp, frame_signal)
    
    #Step 9: Update feature buffers (60-second sliding window per student)
    feature_buffer.add_student_features(timestamp, students)
    
    #Cleanup inactive students (no updates for 5 minutes)
    removed_students = feature_buffer.cleanup_inactive_students(timestamp, timeout=300.0)
    if removed_students:
      print(f"  ! Removed inactive students: {removed_students}")
      # Check out removed students
      if db_enabled:
        for track_id in removed_students:
          db_handler.check_out_student(session_logger.session_name, track_id)
    
    # Get current behavioral metrics and summary (for visual overlay)
    current_behavioral_metrics = None
    current_metrics_summary = None
    
    #Output frame summary
    summary = frame_signal.get_summary()
    print(
      f"[{timestamp:6.2f}s] Frame #{frame_count} | "
      f"Students: {summary['total_students']} | "
      f"Phones: {summary['students_with_phones']} | "
      f"Looking away: {summary['students_looking_away']} | "
      f"Distraction rate: {summary['distraction_rate']:.2%}"
    )
    
    #Output buffered statistics (20-second window analysis)
    if frame_count % 10 == 0:  # Aggregate every 10 frames for faster phone detection response
      print("  [20s Window Analysis & Behavioral Metrics]")
      all_stats = feature_buffer.get_all_statistics()
      
      # Aggregate temporal data into behavioral metrics with raw phone risk
      behavioral_metrics = aggregation_pipeline.aggregate_all(timestamp, all_stats, student_phone_risk)
      
      # Store for visual overlay
      current_behavioral_metrics = behavioral_metrics
      
      # Log behavioral metrics
      session_logger.log_behavioral_metrics(timestamp, frame_count, behavioral_metrics)
      
      # Send metrics to API: immediately on first detection, then every 5 minutes per student
      if db_enabled:
        for track_id, metrics in behavioral_metrics.items():
          # Check if this is first time seeing this student or 5 minutes have passed
          last_send = last_api_metric_send_per_student.get(track_id, 0.0)
          time_since_last_send = timestamp - last_send
          
          if time_since_last_send >= api_metric_interval:
            print(f"  [API SEND] Sending metrics for Student #{track_id} at {timestamp:.2f}s")
            db_handler.insert_metrics(
                session_logger.session_name, track_id, 
                timestamp, frame_count, metrics
            )
            # Update student last_seen and identity
            db_handler.insert_or_update_student(
                session_logger.session_name, track_id, metrics.identity_name
            )
            # Update attendance record with identity
            db_handler.update_attendance(
                session_logger.session_name, track_id, metrics.identity_name
            )
            
            # Check if 5 minutes have passed for periodic attendance with identity
            if track_id in last_attendance_time:
              time_since_last = timestamp - last_attendance_time[track_id]
              if time_since_last >= ATTENDANCE_INTERVAL:
                db_handler.check_in_student(session_logger.session_name, track_id, metrics.identity_name)
                last_attendance_time[track_id] = timestamp
                identity_str = metrics.identity_name or f"Student #{track_id}"
                print(f"✓ Periodic attendance recorded for {identity_str} ({time_since_last/60:.1f} min)")
            
            last_api_metric_send_per_student[track_id] = timestamp
      
      # Get summary and high-risk students
      metrics_summary = aggregation_pipeline.get_metrics_summary(behavioral_metrics)
      current_metrics_summary = metrics_summary
      high_risk_students = aggregation_pipeline.get_high_risk_students(behavioral_metrics)
      
      print(f"    Overall: avg_risk={metrics_summary['avg_engagement_risk']:.1%} | "
            f"high_risk={metrics_summary['high_risk_students']} | "
            f"avg_phone_risk={metrics_summary['avg_phone_risk']:.1%}")
      
      # Output behavioral metrics for each student
      for track_id in sorted(behavioral_metrics.keys()):
        metrics = behavioral_metrics[track_id]
        risk_marker = "⚠️ " if metrics.engagement_risk_level == "high" else "  "
        student_ref = metrics.identity_name or f"Student #{track_id}"
        print(
          f"    {risk_marker}{student_ref}: "
          f"behavior={metrics.primary_behavior} | "
          f"risk={metrics.engagement_risk_level} ({metrics.engagement_risk_score:.2f}) | "
          f"attention={metrics.attention_score:.2f} | "
          f"phone_risk={metrics.phone_risk_score:.2f} ({metrics.phone_trend})"
        )
      
      # Step 10: Rule-based inference - generate behavioral alerts
      all_alerts = rule_engine.evaluate_all(behavioral_metrics)
      
      # Log alerts
      if all_alerts:
        session_logger.log_alerts(timestamp, frame_count, all_alerts)
        
        # Log alerts to MySQL
        if db_enabled:
          for track_id, alerts in all_alerts.items():
            for alert in alerts:
              db_handler.insert_alert(
                  session_logger.session_name, track_id,
                  timestamp, frame_count, alert
              )
        
        # Add critical alerts to visual overlay
        for track_id, alerts in all_alerts.items():
          for alert in alerts:
            if alert.alert_level.value == "critical":
              visual_overlay.add_alert(timestamp, alert)
      
      if all_alerts:
        alert_summary = rule_engine.get_summary(all_alerts)
        print(f"\n  [🔔 Behavioral Alerts: {alert_summary['total_alerts']} total, "
              f"{alert_summary['critical_alerts']} critical, "
              f"{alert_summary['warning_alerts']} warnings]")
        
        # Display critical alerts prominently
        critical_alerts = rule_engine.get_critical_alerts(all_alerts)
        if critical_alerts:
          print("  🚨 CRITICAL ALERTS:")
          for alert in critical_alerts:
            student_ref = alert.identity_name or f"Student #{alert.track_id}"
            print(f"    → {student_ref}: {alert.message}")
            print(f"      Action: {alert.recommended_action}")
        
        # Display warning alerts
        for track_id, alerts in all_alerts.items():
          warning_alerts = [a for a in alerts if a.alert_level.value == "warning"]
          if warning_alerts:
            # Get identity from first alert
            student_ref = warning_alerts[0].identity_name or f"Student #{track_id}"
            print(f"  ⚠️  {student_ref} warnings:")
            for alert in warning_alerts:
              print(f"      - {alert.message}")
      else:
        print("\n  [✓ No behavioral alerts - all students appear engaged]")
    
    #Output individual student details
    for student in students:
      print(
        f"  └─ Student #{student['track_id']} | "
        f"head={student['head_direction']} | "
        f"name={student.get('identity_name') or 'unknown'} | "
        f"phone={student['phone_detected']}"
      )
    
    # Visual overlay rendering
    frame = visual_overlay.render_full_overlay(
      frame=frame,
      students=students,
      frame_summary=summary,
      timestamp=timestamp,
      fps=current_fps,
      behavioral_metrics=current_behavioral_metrics,
      metrics_summary=current_metrics_summary,
      show_head_arrows=False  # Set to True to show direction arrows
    )
    
    # Log the annotated frame to video (always, regardless of window display)
    session_logger.log_frame_video(frame)
    
    if show_window:
      
      try:
        cv2.imshow("Behavior Analysis", frame)
        if cv2.waitKey(1) & 0xFF == config["debug"]["exit_key"]:
          break
      except Exception as e:
        print(f"⚠ Warning: Unable to display window ({e}). Disabling display.")
        show_window = False
        # Fallback: save a rolling preview image
        preview_path = os.path.join(session_logger.session_dir, "preview.jpg")
        try:
          cv2.imwrite(preview_path, frame)
          print(f"  Saved preview frame to: {preview_path}")
        except Exception:
          pass
  
  # Finalize session and generate summary
  final_timestamp = time.time() - start_time
  session_logger.finalize_session(final_timestamp)
  
  # Finalize session in MySQL
  if db_enabled:
    db_handler.finalize_session(
        session_logger.session_name,
        final_timestamp,
        frame_count,
        len(students_tracked)
    )
    
    # Print attendance summary
    print("\n[ATTENDANCE SUMMARY]")
    attendance_records = db_handler.get_attendance_summary(session_logger.session_name)
    if attendance_records:
      print(f"  Total attendees: {len(attendance_records)}")
      print("  " + "="*70)
      for record in attendance_records:
        student_ref = record['identity_name'] or f"Student #{record['track_id']}"
        duration_min = record['duration_seconds'] / 60 if record['duration_seconds'] else 0
        status_icon = "✓" if record['status'] == 'left' else "⟳"
        print(f"  {status_icon} {student_ref:20s} | In: {record['check_in_time']} | Duration: {duration_min:.1f} min")
    
    # Print database summary
    print("\n[API SUMMARY]")
    print(f"  Session logs sent to: https://attcam.cc/api/logs")
    print(f"  Session ID: {session_logger.session_name}")
      
  cap.release()
  cv2.destroyAllWindows()
  
  # Close database connection
  if db_enabled:
    db_handler.close()
  
  print("Pipeline ended")
  
if __name__ == "__main__":
  main()