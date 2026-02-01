"""Analytics and reporting queries for MySQL database."""
import MySQLdb
from typing import List, Dict, Optional


class MySQLAnalytics:
    """Advanced analytics queries for behavioral data."""
    
    def __init__(self, mysql_handler):
        """
        Initialize analytics with existing MySQL handler.
        
        Args:
            mysql_handler: MySQLHandler instance
        """
        self.handler = mysql_handler
    
    def get_student_metrics(self, session_id: str, track_id: int) -> List[Dict]:
        """
        Get all metrics for a specific student in a session.
        
        Args:
            session_id (str): Session identifier
            track_id (int): Student track ID
        
        Returns:
            List of metric records
        """
        try:
            with self.handler.get_cursor() as cursor:
                sql = """
                SELECT timestamp, attention_score, phone_risk_score, 
                       engagement_risk_level, primary_behavior
                FROM behavioral_metrics
                WHERE session_id = %s AND track_id = %s
                ORDER BY timestamp ASC
                """
                cursor.execute(sql, (session_id, track_id))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except MySQLdb.Error as e:
            print(f"✗ Error fetching student metrics: {e}")
            return []
    
    def get_high_risk_students(self, session_id: str) -> List[Dict]:
        """
        Get students with high-risk behavior alerts.
        
        Args:
            session_id (str): Session identifier
        
        Returns:
            List of high-risk students with alert counts
        """
        try:
            with self.handler.get_cursor() as cursor:
                sql = """
                SELECT track_id, COUNT(*) as critical_alert_count
                FROM alerts
                WHERE session_id = %s AND alert_level = 'critical'
                GROUP BY track_id
                ORDER BY critical_alert_count DESC
                """
                cursor.execute(sql, (session_id,))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except MySQLdb.Error as e:
            print(f"✗ Error fetching high-risk students: {e}")
            return []
    
    def get_session_summary(self, session_id: str) -> Optional[Dict]:
        """
        Get complete summary for a session.
        
        Args:
            session_id (str): Session identifier
        
        Returns:
            Session summary dict
        """
        try:
            with self.handler.get_cursor() as cursor:
                sql = """
                SELECT s.session_id, s.start_time, s.end_time, s.duration_seconds,
                       s.total_frames, s.total_students,
                       COUNT(DISTINCT a.track_id) as students_with_alerts,
                       COUNT(CASE WHEN a.alert_level = 'critical' THEN 1 END) as critical_alerts,
                       COUNT(CASE WHEN a.alert_level = 'warning' THEN 1 END) as warning_alerts
                FROM sessions s
                LEFT JOIN alerts a ON s.session_id = a.session_id
                WHERE s.session_id = %s
                GROUP BY s.session_id
                """
                cursor.execute(sql, (session_id,))
                columns = [desc[0] for desc in cursor.description]
                result = cursor.fetchone()
                return dict(zip(columns, result)) if result else None
        except MySQLdb.Error as e:
            print(f"✗ Error fetching session summary: {e}")
            return None
    
    def get_student_behavior_trend(self, track_id: int, days: int = 7) -> List[Dict]:
        """
        Get student behavior trend across multiple sessions.
        
        Args:
            track_id (int): Student track ID
            days (int): Number of past days to analyze
        
        Returns:
            List of sessions with aggregated metrics
        """
        try:
            with self.handler.get_cursor() as cursor:
                sql = """
                SELECT s.session_id, s.start_time,
                       AVG(m.attention_score) as avg_attention,
                       AVG(m.phone_risk_score) as avg_phone_risk,
                       COUNT(CASE WHEN a.alert_level = 'critical' THEN 1 END) as critical_alerts,
                       COUNT(a.id) as total_alerts
                FROM sessions s
                JOIN behavioral_metrics m ON s.session_id = m.session_id
                LEFT JOIN alerts a ON s.session_id = a.session_id 
                    AND m.track_id = a.track_id
                WHERE m.track_id = %s 
                AND s.start_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY s.session_id
                ORDER BY s.start_time DESC
                """
                cursor.execute(sql, (track_id, days))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except MySQLdb.Error as e:
            print(f"✗ Error fetching student trend: {e}")
            return []
    
    def get_all_sessions(self, limit: int = 50) -> List[Dict]:
        """
        Get all recent sessions.
        
        Args:
            limit (int): Maximum number of sessions to return
        
        Returns:
            List of session records
        """
        try:
            with self.handler.get_cursor() as cursor:
                sql = """
                SELECT session_id, start_time, end_time, duration_seconds,
                       total_frames, total_students
                FROM sessions
                ORDER BY start_time DESC
                LIMIT %s
                """
                cursor.execute(sql, (limit,))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except MySQLdb.Error as e:
            print(f"✗ Error fetching sessions: {e}")
            return []
    
    def get_alerts_for_student(self, session_id: str, track_id: int) -> List[Dict]:
        """
        Get all alerts for a specific student in a session.
        
        Args:
            session_id (str): Session identifier
            track_id (int): Student track ID
        
        Returns:
            List of alert records
        """
        try:
            with self.handler.get_cursor() as cursor:
                sql = """
                SELECT timestamp, alert_type, alert_level, message
                FROM alerts
                WHERE session_id = %s AND track_id = %s
                ORDER BY timestamp ASC
                """
                cursor.execute(sql, (session_id, track_id))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except MySQLdb.Error as e:
            print(f"✗ Error fetching alerts: {e}")
            return []
    
    def get_alert_statistics(self, session_id: str) -> Dict:
        """
        Get alert statistics for a session.
        
        Args:
            session_id (str): Session identifier
        
        Returns:
            Alert statistics dict
        """
        try:
            with self.handler.get_cursor() as cursor:
                sql = """
                SELECT 
                    COUNT(*) as total_alerts,
                    COUNT(CASE WHEN alert_level = 'critical' THEN 1 END) as critical,
                    COUNT(CASE WHEN alert_level = 'warning' THEN 1 END) as warning,
                    COUNT(DISTINCT alert_type) as unique_types,
                    COUNT(DISTINCT track_id) as students_with_alerts
                FROM alerts
                WHERE session_id = %s
                """
                cursor.execute(sql, (session_id,))
                columns = [desc[0] for desc in cursor.description]
                result = cursor.fetchone()
                return dict(zip(columns, result)) if result else {}
        except MySQLdb.Error as e:
            print(f"✗ Error fetching alert statistics: {e}")
            return {}
    
    def get_most_common_alerts(self, session_id: str, limit: int = 5) -> List[Dict]:
        """
        Get most common alert types in a session.
        
        Args:
            session_id (str): Session identifier
            limit (int): Number of top alerts to return
        
        Returns:
            List of alert types with counts
        """
        try:
            with self.handler.get_cursor() as cursor:
                sql = """
                SELECT alert_type, COUNT(*) as count
                FROM alerts
                WHERE session_id = %s
                GROUP BY alert_type
                ORDER BY count DESC
                LIMIT %s
                """
                cursor.execute(sql, (session_id, limit))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except MySQLdb.Error as e:
            print(f"✗ Error fetching common alerts: {e}")
            return []
