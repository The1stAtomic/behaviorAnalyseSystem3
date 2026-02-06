"""Feature buffer with sliding window for temporal analysis per student."""
from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class BufferedFeature:
    """A single feature snapshot with timestamp."""
    timestamp: float
    head_direction: str
    phone_detected: bool
    confidence: float
    bbox: tuple  # [x1, y1, x2, y2]
    identity_name: Optional[str] = None


class StudentFeatureBuffer:
    """Maintains a sliding window buffer of features for a single student."""
    
    def __init__(self, track_id, window_size=60.0):
        """
        Args:
            track_id (int): Student's unique tracking ID
            window_size (float): Time window in seconds (default 60s)
        """
        self.track_id = track_id
        self.window_size = window_size
        self.features = deque()  # Stores BufferedFeature objects
        self.last_update = None
    
    def add_feature(self, timestamp, head_direction, phone_detected, confidence, bbox, identity_name=None):
        """Add a feature to the buffer, automatically removing old entries."""
        feature = BufferedFeature(
            timestamp=timestamp,
            head_direction=head_direction,
            phone_detected=phone_detected,
            confidence=confidence,
            bbox=bbox,
            identity_name=identity_name
        )
        self.features.append(feature)
        self.last_update = timestamp
        
        # Remove features outside the sliding window
        self._prune_old_features(timestamp)
    
    def _prune_old_features(self, current_timestamp):
        """Remove features older than window_size."""
        cutoff_time = current_timestamp - self.window_size
        while self.features and self.features[0].timestamp < cutoff_time:
            self.features.popleft()
    
    def get_features(self):
        """Get all features currently in the buffer."""
        return list(self.features)
    
    def get_statistics(self):
        """Compute statistics from buffered features."""
        if not self.features:
            return {
                "track_id": self.track_id,
                "feature_count": 0,
                "avg_confidence": 0.0,
                "phone_detection_rate": 0.0,
                "head_direction_distribution": {},
                "last_update": self.last_update
            }
        
        features_list = list(self.features)
        total = len(features_list)
        
        # Phone detection rate
        phone_detections = sum(1 for f in features_list if f.phone_detected)
        phone_rate = phone_detections / total if total > 0 else 0.0
        
        # Average confidence
        avg_conf = sum(f.confidence for f in features_list) / total if total > 0 else 0.0
        
        # Head direction distribution
        direction_count = defaultdict(int)
        for f in features_list:
            direction_count[f.head_direction] += 1
        
        direction_dist = {
            direction: (count / total)
            for direction, count in direction_count.items()
        }
        
        # Get most recent head direction for immediate attention response
        most_recent_direction = features_list[-1].head_direction if features_list else None
        
        return {
            "track_id": self.track_id,
            "feature_count": total,
            "time_span": features_list[-1].timestamp - features_list[0].timestamp if len(features_list) > 1 else 0.0,
            "avg_confidence": round(avg_conf, 3),
            "phone_detection_rate": round(phone_rate, 3),
            "phone_detections": phone_detections,
            "head_direction_distribution": {k: round(v, 3) for k, v in direction_dist.items()},
            "most_recent_direction": most_recent_direction,
            "last_update": self.last_update,
            "identity_name": features_list[-1].identity_name if features_list else None
        }


class FeatureBuffer:
    """Manages feature buffers for all tracked students."""
    
    def __init__(self, window_size=60.0):
        """
        Args:
            window_size (float): Time window in seconds for all buffers (default 60s)
        """
        self.window_size = window_size
        self.buffers: Dict[int, StudentFeatureBuffer] = {}  # track_id -> StudentFeatureBuffer
    
    def add_student_features(self, timestamp, student_data):
        """
        Add features for multiple students from a frame.
        
        Args:
            timestamp (float): Current frame timestamp
            student_data (list): List of dicts with keys:
                - track_id
                - head_direction
                - phone_detected
                - confidence
                - bbox
        """
        for student in student_data:
            track_id = student.get("track_id")
            
            # Create buffer for this student if it doesn't exist
            if track_id not in self.buffers:
                self.buffers[track_id] = StudentFeatureBuffer(track_id, self.window_size)
            
            # Add feature to student's buffer
            self.buffers[track_id].add_feature(
                timestamp=timestamp,
                head_direction=student.get("head_direction", "unknown"),
                phone_detected=student.get("phone_detected", False),
                confidence=student.get("confidence", 0.0),
                bbox=student.get("bbox", (0, 0, 0, 0)),
                identity_name=student.get("identity_name")
            )
    
    def get_student_buffer(self, track_id) -> Optional[StudentFeatureBuffer]:
        """Get buffer for a specific student."""
        return self.buffers.get(track_id)
    
    def get_all_buffers(self) -> Dict[int, StudentFeatureBuffer]:
        """Get all student buffers."""
        return self.buffers
    
    def get_all_statistics(self):
        """Get statistics for all students."""
        return {
            track_id: buffer.get_statistics()
            for track_id, buffer in self.buffers.items()
        }
    
    def get_student_statistics(self, track_id) -> Optional[dict]:
        """Get statistics for a specific student."""
        if track_id in self.buffers:
            return self.buffers[track_id].get_statistics()
        return None
    
    def cleanup_inactive_students(self, current_timestamp, timeout=300.0):
        """
        Remove students who haven't been updated in a while.
        
        Args:
            current_timestamp (float): Current time
            timeout (float): Time in seconds before considering student inactive
        
        Returns:
            list: Track IDs of removed students
        """
        removed = []
        to_remove = []
        
        for track_id, buffer in self.buffers.items():
            if buffer.last_update is None:
                continue
            
            time_since_update = current_timestamp - buffer.last_update
            if time_since_update > timeout:
                to_remove.append(track_id)
                removed.append(track_id)
        
        for track_id in to_remove:
            del self.buffers[track_id]
        
        return removed
