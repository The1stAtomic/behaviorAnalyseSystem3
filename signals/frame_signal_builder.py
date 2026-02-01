"""Frame-level signal builder for behavior analysis pipeline."""


class StudentSignal:
    """Represents signal data for a single student in a frame."""
    
    def __init__(self, student_id, bbox, head_direction, phone_detected, confidence, identity_name=None, identity_score=None):
        self.id = student_id
        self.bbox = bbox  # [x1, y1, x2, y2]
        self.head_direction = head_direction
        self.phone_detected = phone_detected
        self.confidence = confidence
        self.identity_name = identity_name
        self.identity_score = identity_score
    
    def to_dict(self):
        """Convert to dictionary format."""
        return {
            "id": self.id,
            "bbox": self.bbox,
            "head_direction": self.head_direction,
            "phone_detected": self.phone_detected,
            "confidence": self.confidence,
            "identity_name": self.identity_name,
            "identity_score": self.identity_score
        }


class FrameSignal:
    """Represents all signal data for a single frame."""
    
    def __init__(self, frame_id, timestamp):
        self.frame_id = frame_id
        self.timestamp = timestamp
        self.students = []  # List of StudentSignal objects
    
    def add_student_signal(self, student_signal):
        """Add a student signal to this frame."""
        self.students.append(student_signal)
    
    def get_summary(self):
        """Compute summary statistics for this frame."""
        if not self.students:
            return {
                "total_students": 0,
                "students_with_phones": 0,
                "students_looking_away": 0,
                "avg_confidence": 0.0,
                "distraction_rate": 0.0
            }
        
        total = len(self.students)
        with_phones = sum(1 for s in self.students if s.phone_detected)
        looking_away = sum(1 for s in self.students if s.head_direction != "forward")
        avg_conf = sum(s.confidence for s in self.students) / total
        distraction_rate = (with_phones + looking_away) / (total * 2)
        
        return {
            "total_students": total,
            "students_with_phones": with_phones,
            "students_looking_away": looking_away,
            "avg_confidence": round(avg_conf, 3),
            "distraction_rate": round(distraction_rate, 3)
        }
    
    def to_dict(self):
        """Convert to dictionary format."""
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "students": [s.to_dict() for s in self.students],
            "summary": self.get_summary()
        }


class FrameSignalBuilder:
    """Builds frame-level signals from detection and tracking results."""
    
    def __init__(self):
        self.current_signal = None
    
    def build(self, frame_id, timestamp, tracked_students):
        """
        Build a complete frame signal from tracked student data.
        
        Args:
            frame_id (int): Current frame number
            timestamp (float): Elapsed time in seconds
            tracked_students (list): List of dicts with keys:
                - track_id
                - bbox
                - head_direction
                - phone_detected (bool)
                - confidence
        
        Returns:
            FrameSignal: The constructed frame signal
        """
        signal = FrameSignal(frame_id, timestamp)
        
        for student in tracked_students:
            student_signal = StudentSignal(
                student_id=student.get("track_id"),
                bbox=student.get("bbox"),
                head_direction=student.get("head_direction"),
                phone_detected=student.get("phone_detected", False),
                confidence=student.get("confidence", 0.0),
                identity_name=student.get("identity_name"),
                identity_score=student.get("identity_score")
            )
            signal.add_student_signal(student_signal)
        
        self.current_signal = signal
        return signal
    
    def get_current_signal(self):
        """Get the most recently built signal."""
        return self.current_signal
