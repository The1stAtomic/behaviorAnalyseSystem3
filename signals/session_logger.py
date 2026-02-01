"""Output layer for logging behavioral analysis results to files."""
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import os
import numpy as np
import cv2


def convert_to_serializable(obj):
    """Convert NumPy types to Python native types for JSON serialization."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_to_serializable(item) for item in obj)
    return obj


class VideoWriter:
    """Writes annotated frames to a video file."""
    
    def __init__(self, output_path: str, fps: float = 30.0, frame_size: tuple = None):
        """
        Initialize video writer.
        
        Args:
            output_path (str): Path to save the video file
            fps (float): Frames per second for output video
            frame_size (tuple): (width, height) of frames. Required before writing frames.
        """
        self.output_path = output_path
        self.fps = fps
        self.frame_size = frame_size
        self.writer = None
        self.frame_count = 0
        self.is_initialized = False
        
        # Create parent directory if it doesn't exist
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    def init_with_frame(self, frame: np.ndarray):
        """
        Initialize the VideoWriter with the first frame's dimensions.
        
        Args:
            frame (np.ndarray): First frame to determine dimensions
        """
        if not self.is_initialized:
            height, width = frame.shape[:2]
            self.frame_size = (width, height)
            
            # Use H.264 codec for MP4 format
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.writer = cv2.VideoWriter(self.output_path, fourcc, self.fps, self.frame_size)
            
            if not self.writer.isOpened():
                raise RuntimeError(f"Failed to initialize VideoWriter for {self.output_path}")
            
            self.is_initialized = True
            print(f"Video writer initialized: {self.output_path} ({width}x{height}@{self.fps}fps)")
    
    def write_frame(self, frame: np.ndarray):
        """
        Write a frame to the video file.
        
        Args:
            frame (np.ndarray): Frame to write
        """
        if not self.is_initialized:
            self.init_with_frame(frame)
        
        # Ensure frame matches expected size
        if frame.shape[:2] != (self.frame_size[1], self.frame_size[0]):
            # Resize if necessary
            frame = cv2.resize(frame, self.frame_size)
        
        if not self.writer.write(frame):
            print(f"Warning: Failed to write frame {self.frame_count} to video")
        
        self.frame_count += 1
    
    def release(self):
        """Release the video writer and close the file."""
        if self.writer is not None:
            self.writer.release()
            print(f"Video written: {self.output_path} ({self.frame_count} frames)")
            self.is_initialized = False


class SessionLogger:
    """Manages logging of behavioral analysis session data to various formats."""
    
    def __init__(self, session_name: Optional[str] = None, output_dir: str = "log", fps: float = 30.0):
        """
        Initialize session logger.
        
        Args:
            session_name (str): Name for this session (defaults to timestamp)
            output_dir (str): Directory to save log files
            fps (float): Frames per second for output video
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Generate session name if not provided
        if session_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_name = f"session_{timestamp}"
        
        self.session_name = session_name
        self.session_start_time = datetime.now()
        self.fps = fps
        
        # Create session subdirectory
        self.session_dir = self.output_dir / session_name
        self.session_dir.mkdir(exist_ok=True)
        
        # Initialize file paths
        self.frame_log_path = self.session_dir / "frame_log.jsonl"  # JSON Lines format
        self.alert_log_path = self.session_dir / "alerts.jsonl"
        self.metrics_csv_path = self.session_dir / "metrics.csv"
        self.summary_path = self.session_dir / "session_summary.txt"
        self.session_json_path = self.session_dir / "session_data.json"
        self.video_path = self.session_dir / "detection_analysis.mp4"
        
        # Initialize video writer (will be initialized with first frame)
        self.video_writer = VideoWriter(str(self.video_path), fps=fps)
        
        # Initialize CSV files with headers
        self._init_metrics_csv()
        
        # Session statistics
        self.frame_count = 0
        self.total_alerts = 0
        self.critical_alerts = 0
        self.students_tracked = set()
        
        # Buffer for session summary
        self.all_frames = []
        self.all_alerts = []
        
        print(f"Session logger initialized: {self.session_dir}")
    
    def _init_metrics_csv(self):
        """Initialize CSV file with headers."""
        with open(self.metrics_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'frame_id', 'track_id', 'behavior', 'engagement_risk_level',
                'engagement_risk_score', 'attention_score', 'looking_away_rate',
                'phone_risk_score', 'phone_detection_rate', 'phone_trend',
                'direction_stability', 'sample_count', 'observation_duration',
                'avg_confidence', 'data_quality'
            ])
    
    def log_frame_data(self, frame_id: int, timestamp: float, frame_signal: any):
        """
        Log frame-level data (frame signal with all students).
        
        Args:
            frame_id (int): Frame number
            timestamp (float): Elapsed time
            frame_signal: FrameSignal object
        """
        frame_data = {
            "frame_id": frame_id,
            "timestamp": round(timestamp, 3),
            "datetime": datetime.now().isoformat(),
            "signal": convert_to_serializable(frame_signal.to_dict())
        }
        
        # Append to JSON Lines file (one JSON object per line)
        with open(self.frame_log_path, 'a') as f:
            f.write(json.dumps(frame_data) + '\n')
        
        self.all_frames.append(frame_data)
        self.frame_count += 1
    
    def log_frame_video(self, frame: np.ndarray):
        """
        Write a frame to the detection analysis video.
        
        Args:
            frame (np.ndarray): Frame with visual overlays to write to video
        """
        if self.video_writer is not None:
            try:
                self.video_writer.write_frame(frame)
            except Exception as e:
                print(f"Warning: Failed to write frame to video: {e}")
    
    def log_behavioral_metrics(self, timestamp: float, frame_id: int, 
                               behavioral_metrics: Dict[int, any]):
        """
        Log behavioral metrics for all students.
        
        Args:
            timestamp (float): Elapsed time
            frame_id (int): Frame number
            behavioral_metrics: Dict of track_id -> BehavioralMetrics
        """
        # Append to CSV
        with open(self.metrics_csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            for track_id, metrics in behavioral_metrics.items():
                self.students_tracked.add(track_id)
                writer.writerow([
                    round(timestamp, 3),
                    frame_id,
                    track_id,
                    metrics.primary_behavior,
                    metrics.engagement_risk_level,
                    round(metrics.engagement_risk_score, 4),
                    round(metrics.attention_score, 4),
                    round(metrics.looking_away_rate, 4),
                    round(metrics.phone_risk_score, 4),
                    round(metrics.phone_detection_rate, 4),
                    metrics.phone_trend,
                    round(metrics.direction_stability, 4),
                    metrics.sample_count,
                    round(metrics.observation_duration, 2),
                    round(metrics.avg_confidence, 4),
                    metrics.data_quality
                ])
    
    def log_alerts(self, timestamp: float, frame_id: int, all_alerts: Dict[int, List[any]]):
        """
        Log behavioral alerts.
        
        Args:
            timestamp (float): Elapsed time
            frame_id (int): Frame number
            all_alerts: Dict of track_id -> List[BehaviorAlert]
        """
        for track_id, alerts in all_alerts.items():
            for alert in alerts:
                alert_data = {
                    "timestamp": round(timestamp, 3),
                    "frame_id": frame_id,
                    "datetime": datetime.now().isoformat(),
                    "alert": convert_to_serializable(alert.to_dict())
                }
                
                # Append to alerts log
                with open(self.alert_log_path, 'a') as f:
                    f.write(json.dumps(alert_data) + '\n')
                
                self.all_alerts.append(alert_data)
                self.total_alerts += 1
                
                if alert.alert_level.value == "critical":
                    self.critical_alerts += 1
    
    def finalize_session(self, end_timestamp: float):
        """
        Finalize the session and generate summary files.
        
        Args:
            end_timestamp (float): Final elapsed time
        """
        session_end_time = datetime.now()
        duration = (session_end_time - self.session_start_time).total_seconds()
        
        # Release video writer
        if self.video_writer is not None:
            self.video_writer.release()
        
        # Generate text summary
        self._generate_text_summary(end_timestamp, duration)
        
        # Generate comprehensive JSON
        self._generate_json_summary(end_timestamp, duration)
        
        print(f"\nSession finalized: {self.session_dir}")
        print(f"  - Video: {self.video_path.name}")
        print(f"  - Frame log: {self.frame_log_path.name}")
        print(f"  - Alert log: {self.alert_log_path.name}")
        print(f"  - Metrics CSV: {self.metrics_csv_path.name}")
        print(f"  - Summary: {self.summary_path.name}")
        print(f"  - JSON data: {self.session_json_path.name}")
    
    def _generate_text_summary(self, end_timestamp: float, duration: float):
        """Generate human-readable text summary."""
        with open(self.summary_path, 'w') as f:
            f.write("=" * 70 + "\n")
            f.write("BEHAVIOR ANALYSIS SESSION SUMMARY\n")
            f.write("=" * 70 + "\n\n")
            
            f.write(f"Session Name: {self.session_name}\n")
            f.write(f"Start Time: {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)\n")
            f.write(f"Elapsed Time: {end_timestamp:.1f} seconds\n\n")
            
            f.write("-" * 70 + "\n")
            f.write("STATISTICS\n")
            f.write("-" * 70 + "\n")
            f.write(f"Total Frames Processed: {self.frame_count}\n")
            f.write(f"Students Tracked: {len(self.students_tracked)}\n")
            f.write(f"Student IDs: {sorted(self.students_tracked)}\n")
            f.write(f"Total Alerts: {self.total_alerts}\n")
            f.write(f"Critical Alerts: {self.critical_alerts}\n")
            f.write(f"Warning/Info Alerts: {self.total_alerts - self.critical_alerts}\n\n")
            
            if self.all_alerts:
                f.write("-" * 70 + "\n")
                f.write("ALERT SUMMARY BY STUDENT\n")
                f.write("-" * 70 + "\n")
                
                # Group alerts by student
                alerts_by_student = {}
                for alert_data in self.all_alerts:
                    track_id = alert_data['alert']['track_id']
                    if track_id not in alerts_by_student:
                        alerts_by_student[track_id] = []
                    alerts_by_student[track_id].append(alert_data)
                
                for track_id in sorted(alerts_by_student.keys()):
                    alerts = alerts_by_student[track_id]
                    critical_count = sum(1 for a in alerts if a['alert']['alert_level'] == 'critical')
                    f.write(f"\nStudent #{track_id}:\n")
                    f.write(f"  Total Alerts: {len(alerts)}\n")
                    f.write(f"  Critical: {critical_count}\n")
                    f.write(f"  Warnings: {len(alerts) - critical_count}\n")
                    
                    # List critical alerts
                    critical = [a for a in alerts if a['alert']['alert_level'] == 'critical']
                    if critical:
                        f.write(f"  Critical Issues:\n")
                        for a in critical:
                            f.write(f"    - [{a['timestamp']:.1f}s] {a['alert']['message']}\n")
            
            f.write("\n" + "=" * 70 + "\n")
            f.write(f"Log files saved to: {self.session_dir}\n")
            f.write("=" * 70 + "\n")
    
    def _generate_json_summary(self, end_timestamp: float, duration: float):
        """Generate comprehensive JSON summary."""
        summary = {
            "session_info": {
                "name": self.session_name,
                "start_time": self.session_start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "duration_seconds": round(duration, 2),
                "elapsed_time_seconds": round(end_timestamp, 2)
            },
            "statistics": {
                "frames_processed": self.frame_count,
                "students_tracked": len(self.students_tracked),
                "student_ids": sorted(list(self.students_tracked)),
                "total_alerts": self.total_alerts,
                "critical_alerts": self.critical_alerts,
                "warning_alerts": self.total_alerts - self.critical_alerts
            },
            "files": {
                "video": str(self.video_path.name),
                "frame_log": str(self.frame_log_path.name),
                "alert_log": str(self.alert_log_path.name),
                "metrics_csv": str(self.metrics_csv_path.name),
                "summary_txt": str(self.summary_path.name)
            }
        }
        
        with open(self.session_json_path, 'w') as f:
            json.dump(summary, f, indent=2)
