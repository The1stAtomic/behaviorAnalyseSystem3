"""API handler for sending behavioral analysis data to remote API."""
import requests
import json
import time
from typing import Optional, List, Dict
from datetime import datetime


class SafeJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle edge cases."""
    def default(self, obj):
        if isinstance(obj, (int, float)):
            if obj != obj:  # NaN check
                return 0.0
            return obj
        return super().default(obj)


class APIHandler:
    """Handles API requests for behavior analysis data persistence."""
    
    def __init__(self, api_url: str = "https://attcam.cc/api/logs", timeout: int = 10):
        """
        Initialize API handler.
        
        Args:
            api_url (str): API endpoint URL
            timeout (int): Request timeout in seconds
        """
        self.api_url = api_url
        self.timeout = timeout
        self.session = requests.Session()
        self.last_error = None
        self.blocked_tracks = {}
        self.block_duration_seconds = 300
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'BehaviorAnalysisSystem/1.0'
        })
        print(f"✓ API Handler initialized: {self.api_url}")
    
    def _make_request(self, payload: Dict) -> bool:
        """
        Make POST request to API.
        
        Args:
            payload (dict): Data to send
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # API requires query and accuracy for ALL requests
            if 'query' not in payload or payload.get('query') is None or payload.get('query') == '':
                payload['query'] = 'SYSTEM'
            
            if 'accuracy' not in payload or payload.get('accuracy') is None:
                payload['accuracy'] = 100.0
            
            # Ensure accuracy is definitely a number
            try:
                payload['accuracy'] = float(payload['accuracy'])
            except (ValueError, TypeError):
                payload['accuracy'] = 100.0
            
            response = self.session.post(
                self.api_url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            self.last_error = None
            return True
        except requests.exceptions.RequestException as e:
            print(f"✗ API request error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_json = e.response.json()
                    print(f"  Response: {error_json}")
                except:
                    error_json = None
                    print(f"  Response: {e.response.text}")
                self.last_error = {
                    "status_code": getattr(e.response, "status_code", None),
                    "json": error_json,
                    "text": getattr(e.response, "text", None),
                    "url": getattr(e.response, "url", None)
                }
            else:
                self.last_error = {
                    "status_code": None,
                    "json": None,
                    "text": str(e),
                    "url": None
                }
            return False
    
    def insert_session(self, session_id: str):
        """
        Create a new session record.
        
        Args:
            session_id (str): Unique session identifier
        """
        payload = {
            "event_type": "session_start",
            "session_id": session_id,
            "query": "SYSTEM",
            "accuracy": 100.0,
            "timestamp": datetime.now().isoformat()
        }
        if self._make_request(payload):
            print(f"✓ Session {session_id} sent to API")
    
    def insert_metrics(self, session_id: str, track_id: int, timestamp: float, 
                      frame_id: int, metrics):
        """
        Send behavioral metrics to API.
        
        Args:
            session_id (str): Session identifier
            track_id (int): Student track ID
            timestamp (float): Elapsed time
            frame_id (int): Frame number
            metrics: BehavioralMetrics object
        """
        try:
            now = time.time()
            blocked_until = self.blocked_tracks.get(int(track_id))
            if blocked_until and now < blocked_until:
                return

            # Ensure required fields have values
            identity_name = getattr(metrics, 'identity_name', None)
            # Use student name as query when available, fall back to track-based id
            query_name = str(identity_name) if identity_name else f"Unknown{track_id:03d}"
            
            # Get accuracy with multiple fallbacks
            confidence = getattr(metrics, 'avg_confidence', None)
            if confidence is not None:
                accuracy = float(confidence) * 100
            else:
                accuracy = 95.5
            
            # Ensure accuracy is a valid float (not NaN, not None)
            if accuracy != accuracy:  # NaN check
                accuracy = 95.5
            accuracy = float(accuracy)
            
            # Simple metrics for API: binary/categorical instead of continuous
            phone_risk = 100.0 if getattr(metrics, 'phone_risk_score', 0.0) > 0.0 else 0.0
            
            # Attention: apply the same binary logic as phone_risk_score
            attention = getattr(metrics, 'attention_score', 0.0)
            has_phone = phone_risk > 0.0
            is_forward = attention > 0.0
            attention_score = 100.0 if (is_forward or not has_phone) else 0.0

            # Looking away: 0 if forward, 100 if not
            looking_away_rate = 0.0 if is_forward else 100.0

            # Engagement risk: high if has phone or looking away, low otherwise
            engagement_risk_score = 100.0 if (has_phone or not is_forward) else 0.0
            engagement_risk_level = "high" if engagement_risk_score > 50.0 else "low"
            
            payload = {
                "query": query_name,
                "accuracy": accuracy,
                "track_id": int(track_id),
                "timestamp": float(timestamp),
                "frame_id": int(frame_id),
                "identity_name": str(identity_name) if identity_name else None,
                "attention_score": attention_score,
                "looking_away_rate": looking_away_rate,
                "phone_risk_score": phone_risk,
                "phone_detection_rate": float(getattr(metrics, 'phone_detection_rate', 0.0)),
                "engagement_risk_score": engagement_risk_score,
                "engagement_risk_level": engagement_risk_level,
                "primary_behavior": str(getattr(metrics, 'primary_behavior', 'Unknown')),
                "direction_stability": float(getattr(metrics, 'direction_stability', 0.0)),
                "data_quality": str(getattr(metrics, 'data_quality', 'Unknown')),
                "session_id": str(session_id)
            }
            print(
                "🔍 insert_metrics payload before send: "
                f"query={repr(payload['query'])}, "
                f"accuracy={repr(payload['accuracy'])}, "
                f"identity_name={repr(payload.get('identity_name'))}"
            )
            if not self._make_request(payload):
                # Auto-enroll/check-in on known enrollment errors, then retry once
                err = self.last_error or {}
                status_code = err.get("status_code")
                message = None
                if isinstance(err.get("json"), dict):
                    message = err.get("json", {}).get("message")
                if status_code == 404 and message in {"Student not found", "Not enrolled today"}:
                    print("  ↻ Attempting auto-enroll/check-in before retry...")
                    try:
                        self.insert_or_update_student(session_id, track_id, identity_name)
                        self.check_in_student(session_id, track_id, identity_name)
                    except Exception:
                        pass
                    if not self._make_request(payload) and message == "Not enrolled today":
                        self.blocked_tracks[int(track_id)] = now + self.block_duration_seconds
                elif status_code == 404 and message == "Not enrolled today":
                    self.blocked_tracks[int(track_id)] = now + self.block_duration_seconds
            else:
                if int(track_id) in self.blocked_tracks:
                    del self.blocked_tracks[int(track_id)]
        except Exception as e:
            print(f"✗ Error preparing metrics payload: {e}")
            import traceback
            traceback.print_exc()
    
    def insert_alert(self, session_id: str, track_id: int, timestamp: float, 
                    frame_id: int, alert):
        """
        Send behavioral alert to API.
        
        Args:
            session_id (str): Session identifier
            track_id (int): Student track ID
            timestamp (float): Elapsed time
            frame_id (int): Frame number
            alert: BehaviorAlert object
        """
        payload = {
            "event_type": "alert",
            "query": alert.identity_name or f"STU{track_id:03d}",
            "accuracy": 100.0,
            "track_id": track_id,
            "timestamp": timestamp,
            "frame_id": frame_id,
            "alert_type": alert.alert_type.value,
            "alert_level": alert.alert_level.value,
            "message": alert.message,
            "identity_name": alert.identity_name,
            "session_id": session_id
        }
        self._make_request(payload)
    
    def insert_or_update_student(self, session_id: str, track_id: int, identity_name: Optional[str] = None):
        """
        Send student tracking record to API.
        
        Args:
            session_id (str): Session identifier
            track_id (int): Student track ID in this session
            identity_name (str): Recognized identity (optional)
        """
        query = identity_name if identity_name else f"STU{track_id:03d}"
        payload = {
            "event_type": "student_tracking",
            "session_id": session_id,
            "track_id": track_id,
            "query": str(query),
            "accuracy": 100.0,
            "identity_name": identity_name,
            "timestamp": datetime.now().isoformat()
        }
        self._make_request(payload)
    
    def check_in_student(self, session_id: str, track_id: int, identity_name: Optional[str] = None):
        """
        Send student check-in record to API.
        
        Args:
            session_id (str): Session identifier
            track_id (int): Student track ID
            identity_name (str): Recognized identity (optional)
        """
        try:
            query = identity_name if identity_name else f"STU{track_id:03d}"
            payload = {
                "event_type": "check_in",
                "session_id": str(session_id),
                "track_id": int(track_id),
                "query": str(query),
                "identity_name": str(identity_name) if identity_name else None,
                "timestamp": datetime.now().isoformat()
            }
            if self._make_request(payload):
                if int(track_id) in self.blocked_tracks:
                    del self.blocked_tracks[int(track_id)]
                print(f"✓ Check-in sent: {identity_name or f'Student #{track_id}'}")
        except Exception as e:
            print(f"✗ Error sending check-in: {e}")
    
    def update_attendance(self, session_id: str, track_id: int, identity_name: Optional[str] = None):
        """
        Update attendance record via API.
        
        Args:
            session_id (str): Session identifier
            track_id (int): Student track ID
            identity_name (str): Recognized identity (optional)
        """
        payload = {
            "event_type": "attendance_update",
            "session_id": session_id,
            "track_id": track_id,
            "query": identity_name if identity_name else f"STU{track_id:03d}",
            "identity_name": identity_name,
            "timestamp": datetime.now().isoformat()
        }
        self._make_request(payload)
    
    def check_out_student(self, session_id: str, track_id: int):
        """
        Send student check-out record to API.
        
        Args:
            session_id (str): Session identifier
            track_id (int): Student track ID
        """
        payload = {
            "event_type": "check_out",
            "session_id": session_id,
            "track_id": track_id,
            "timestamp": datetime.now().isoformat()
        }
        self._make_request(payload)
    
    def finalize_all_attendance(self, session_id: str):
        """
        Finalize all attendance records for session via API.
        
        Args:
            session_id (str): Session identifier
        """
        payload = {
            "event_type": "finalize_attendance",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        if self._make_request(payload):
            print(f"✓ Finalized attendance for session {session_id}")
    
    def get_attendance_summary(self, session_id: str) -> List[Dict]:
        """
        Get attendance summary from API (optional implementation).
        
        Args:
            session_id (str): Session identifier
        
        Returns:
            List of attendance records (empty if not supported by API)
        """
        try:
            response = self.session.get(
                f"{self.api_url}/attendance/{session_id}",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"✗ Error getting attendance summary: {e}")
            return []
    
    def finalize_session(self, session_id: str, duration: float, 
                        frame_count: int, student_count: int):
        """
        Finalize session via API.
        
        Args:
            session_id (str): Session identifier
            duration (float): Session duration in seconds
            frame_count (int): Total frames processed
            student_count (int): Number of students tracked
        """
        payload = {
            "event_type": "session_end",
            "session_id": session_id,
            "query": "SYSTEM",
            "accuracy": 100.0,
            "duration_seconds": duration,
            "total_frames": frame_count,
            "total_students": student_count,
            "timestamp": datetime.now().isoformat()
        }
        if self._make_request(payload):
            print(f"✓ Session {session_id} finalized via API")
    
    def get_session_exists(self, session_id: str) -> bool:
        """
        Check if a session exists via API.
        
        Args:
            session_id (str): Session identifier
        
        Returns:
            bool: True if session exists (always True for API for robustness)
        """
        try:
            response = self.session.get(
                f"{self.api_url}/session/{session_id}",
                timeout=self.timeout
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return True  # Assume exists to be resilient to API failures
    
    def close(self):
        """Close API session."""
        if self.session:
            self.session.close()
            print("✓ API session closed")