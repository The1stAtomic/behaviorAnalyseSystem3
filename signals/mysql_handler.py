"""MySQL database handler for behavioral analysis data persistence."""
import MySQLdb
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict


class MySQLHandler:
    """Handles MySQL database operations for behavior analysis."""
    
    def __init__(self, host='localhost', port=3307, user='pma', password='', 
                 database='behavior_analysis'):
        """
        Initialize MySQL connection.
        
        Args:
            host (str): MySQL server host
            port (int): MySQL server port
            user (str): MySQL username
            password (str): MySQL password
            database (str): Database name
        """
        self.config = {
            'host': host,
            'port': port,
            'user': user,
            'passwd': password,
            'db': database,
            'charset': 'utf8mb4'
        }
        self.connection = None
        self.connect()
    
    def connect(self):
        """Establish MySQL connection."""
        try:
            self.connection = MySQLdb.connect(**self.config)
            print(f"✓ Connected to MySQL: {self.config['host']}:{self.config['port']}/{self.config['db']}")
        except MySQLdb.Error as e:
            print(f"✗ Error connecting to MySQL: {e}")
            raise
    
    @contextmanager
    def get_cursor(self):
        """Context manager for database cursor."""
        cursor = self.connection.cursor()
        try:
            yield cursor
            self.connection.commit()
        except MySQLdb.Error as e:
            self.connection.rollback()
            print(f"✗ Database error: {e}")
            raise
        finally:
            cursor.close()
    
    def insert_session(self, session_id: str):
        """
        Create a new session record.
        
        Args:
            session_id (str): Unique session identifier
        """
        try:
            with self.get_cursor() as cursor:
                sql = """
                INSERT INTO sessions (session_id, start_time)
                VALUES (%s, NOW())
                """
                cursor.execute(sql, (session_id,))
            print(f"✓ Session {session_id} inserted into database")
        except MySQLdb.Error as e:
            print(f"✗ Error inserting session: {e}")
    
    def insert_metrics(self, session_id: str, track_id: int, timestamp: float, 
                      frame_id: int, metrics):
        """
        Insert behavioral metrics for a student.
        
        Args:
            session_id (str): Session identifier
            track_id (int): Student track ID
            timestamp (float): Elapsed time
            frame_id (int): Frame number
            metrics: BehavioralMetrics object
        """
        try:
            with self.get_cursor() as cursor:
                sql = """
                INSERT INTO behavioral_metrics 
                (session_id, track_id, identity_name, timestamp, frame_id, attention_score, 
                 looking_away_rate, phone_risk_score, phone_detection_rate,
                 engagement_risk_score, engagement_risk_level, primary_behavior,
                 direction_stability, avg_confidence, data_quality)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    session_id, track_id, metrics.identity_name, timestamp, frame_id,
                    metrics.attention_score,
                    metrics.looking_away_rate,
                    metrics.phone_risk_score,
                    metrics.phone_detection_rate,
                    metrics.engagement_risk_score,
                    metrics.engagement_risk_level,
                    metrics.primary_behavior,
                    metrics.direction_stability,
                    metrics.avg_confidence,
                    metrics.data_quality
                ))
        except MySQLdb.Error as e:
            print(f"✗ Error inserting metrics: {e}")
    
    def insert_alert(self, session_id: str, track_id: int, timestamp: float, 
                    frame_id: int, alert):
        """
        Insert behavioral alert.
        
        Args:
            session_id (str): Session identifier
            track_id (int): Student track ID
            timestamp (float): Elapsed time
            frame_id (int): Frame number
            alert: BehaviorAlert object
        """
        try:
            with self.get_cursor() as cursor:
                sql = """
                INSERT INTO alerts 
                (session_id, track_id, identity_name, timestamp, frame_id, alert_type, alert_level, message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    session_id, track_id, alert.identity_name, timestamp, frame_id,
                    alert.alert_type.value,
                    alert.alert_level.value,
                    alert.message
                ))
        except MySQLdb.Error as e:
            print(f"✗ Error inserting alert: {e}")
    
    def insert_or_update_student(self, session_id: str, track_id: int, identity_name: Optional[str] = None):
        """
        Insert or update student tracking record for cross-session analysis.
        
        Args:
            session_id (str): Session identifier
            track_id (int): Student track ID in this session
            identity_name (str): Recognized identity (optional)
        """
        try:
            with self.get_cursor() as cursor:
                # Check if this student already exists in this session
                check_sql = """
                SELECT student_id FROM students 
                WHERE session_id = %s AND track_id = %s
                """
                cursor.execute(check_sql, (session_id, track_id))
                exists = cursor.fetchone()
                
                if exists:
                    # Update last_seen (happens automatically via trigger, but we can update identity if it changed)
                    if identity_name:
                        update_sql = """
                        UPDATE students 
                        SET identity_name = %s, last_seen = NOW()
                        WHERE session_id = %s AND track_id = %s
                        """
                        cursor.execute(update_sql, (identity_name, session_id, track_id))
                else:
                    # Insert new student record
                    insert_sql = """
                    INSERT INTO students (session_id, track_id, identity_name, first_seen, last_seen)
                    VALUES (%s, %s, %s, NOW(), NOW())
                    """
                    cursor.execute(insert_sql, (session_id, track_id, identity_name))
        except MySQLdb.Error as e:
            print(f"✗ Error inserting/updating student: {e}")
    
    def check_in_student(self, session_id: str, track_id: int, identity_name: Optional[str] = None):
        """
        Record student attendance check-in.
        
        Args:
            session_id (str): Session identifier
            track_id (int): Student track ID
            identity_name (str): Recognized identity (optional)
        """
        try:
            with self.get_cursor() as cursor:
                # Check if already checked in
                check_sql = """
                SELECT attendance_id FROM attendance
                WHERE session_id = %s AND track_id = %s AND status = 'present'
                """
                cursor.execute(check_sql, (session_id, track_id))
                if cursor.fetchone():
                    return  # Already checked in
                
                # Insert new attendance record
                insert_sql = """
                INSERT INTO attendance (session_id, track_id, identity_name, check_in_time, status)
                VALUES (%s, %s, %s, NOW(), 'present')
                """
                cursor.execute(insert_sql, (session_id, track_id, identity_name))
                print(f"✓ Attendance: {identity_name or f'Student #{track_id}'} checked in")
        except MySQLdb.Error as e:
            print(f"✗ Error checking in student: {e}")
    
    def update_attendance(self, session_id: str, track_id: int, identity_name: Optional[str] = None):
        """
        Update attendance record with latest identity and timestamp.
        
        Args:
            session_id (str): Session identifier
            track_id (int): Student track ID
            identity_name (str): Recognized identity (optional)
        """
        try:
            with self.get_cursor() as cursor:
                # Update identity if provided and record still present
                if identity_name:
                    update_sql = """
                    UPDATE attendance
                    SET identity_name = %s, check_out_time = NOW()
                    WHERE session_id = %s AND track_id = %s AND status = 'present'
                    """
                    cursor.execute(update_sql, (identity_name, session_id, track_id))
        except MySQLdb.Error as e:
            print(f"✗ Error updating attendance: {e}")
    
    def check_out_student(self, session_id: str, track_id: int):
        """
        Record student check-out and calculate duration.
        
        Args:
            session_id (str): Session identifier
            track_id (int): Student track ID
        """
        try:
            with self.get_cursor() as cursor:
                update_sql = """
                UPDATE attendance
                SET check_out_time = NOW(),
                    duration_seconds = TIMESTAMPDIFF(SECOND, check_in_time, NOW()),
                    status = 'left'
                WHERE session_id = %s AND track_id = %s AND status = 'present'
                """
                cursor.execute(update_sql, (session_id, track_id))
        except MySQLdb.Error as e:
            print(f"✗ Error checking out student: {e}")
    
    def finalize_all_attendance(self, session_id: str):
        """
        Finalize all attendance records for session (mark as left with duration).
        
        Args:
            session_id (str): Session identifier
        """
        try:
            with self.get_cursor() as cursor:
                update_sql = """
                UPDATE attendance
                SET check_out_time = NOW(),
                    duration_seconds = TIMESTAMPDIFF(SECOND, check_in_time, NOW()),
                    status = 'left'
                WHERE session_id = %s AND status = 'present'
                """
                cursor.execute(update_sql, (session_id,))
                print(f"✓ Finalized attendance for session {session_id}")
        except MySQLdb.Error as e:
            print(f"✗ Error finalizing attendance: {e}")
    
    def get_attendance_summary(self, session_id: str) -> List[Dict]:
        """
        Get attendance summary for a session.
        
        Args:
            session_id (str): Session identifier
        
        Returns:
            List of attendance records with details
        """
        try:
            with self.get_cursor() as cursor:
                sql = """
                SELECT track_id, identity_name, check_in_time, check_out_time, 
                       duration_seconds, status
                FROM attendance
                WHERE session_id = %s
                ORDER BY check_in_time
                """
                cursor.execute(sql, (session_id,))
                columns = ['track_id', 'identity_name', 'check_in_time', 'check_out_time',
                          'duration_seconds', 'status']
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except MySQLdb.Error as e:
            print(f"✗ Error getting attendance summary: {e}")
            return []
    
    def finalize_session(self, session_id: str, duration: float, 
                        frame_count: int, student_count: int):
        """
        Update session with final statistics and finalize attendance.
        
        Args:
            session_id (str): Session identifier
            duration (float): Session duration in seconds
            frame_count (int): Total frames processed
            student_count (int): Number of students tracked
        """
        try:
            with self.get_cursor() as cursor:
                sql = """
                UPDATE sessions 
                SET end_time = NOW(), duration_seconds = %s, 
                    total_frames = %s, total_students = %s
                WHERE session_id = %s
                """
                cursor.execute(sql, (duration, frame_count, student_count, session_id))
            
            # Finalize all attendance records
            self.finalize_all_attendance(session_id)
            
            print(f"✓ Session {session_id} finalized in database")
        except MySQLdb.Error as e:
            print(f"✗ Error finalizing session: {e}")
    
    def get_session_exists(self, session_id: str) -> bool:
        """Check if a session already exists."""
        try:
            with self.get_cursor() as cursor:
                sql = "SELECT session_id FROM sessions WHERE session_id = %s"
                cursor.execute(sql, (session_id,))
                return cursor.fetchone() is not None
        except MySQLdb.Error as e:
            print(f"✗ Error checking session: {e}")
            return False
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            print("✓ MySQL connection closed")
