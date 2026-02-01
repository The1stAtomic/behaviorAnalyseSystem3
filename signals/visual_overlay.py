"""Real-time visual overlay for behavior analysis."""
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple


class VisualOverlay:
    """Draws real-time visual feedback on video frames."""
    
    def __init__(self):
        """Initialize visual overlay with default styling."""
        # Color scheme for risk levels (BGR format)
        self.colors = {
            "low": (0, 255, 0),      # Green
            "medium": (0, 165, 255),  # Orange
            "high": (0, 0, 255),      # Red
            "default": (255, 255, 255)  # White
        }
        
        # Alert colors
        self.alert_colors = {
            "critical": (0, 0, 255),   # Red
            "warning": (0, 165, 255),  # Orange
            "info": (255, 255, 0)      # Cyan
        }
        
        # Font settings
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_scale_small = 0.4
        self.font_scale_medium = 0.5
        self.font_scale_large = 0.6
        self.font_thickness = 1
        self.font_thickness_bold = 2
        
        # Alert display buffer
        self.active_alerts = []
        self.alert_duration = 5.0  # seconds
    
    def draw_student_boxes(self, frame, students, behavioral_metrics: Optional[Dict] = None):
        """
        Draw bounding boxes around students with risk-based coloring.
        
        Args:
            frame: Video frame
            students: List of student dicts with track_id, bbox, head_direction, etc.
            behavioral_metrics: Dict of track_id -> BehavioralMetrics (optional)
        """
        for student in students:
            track_id = student.get("track_id")
            bbox = student.get("bbox")
            
            if bbox is None:
                continue
            
            x1, y1, x2, y2 = map(int, bbox)
            
            # Determine color based on risk level if metrics available
            color = self.colors["default"]
            risk_level = None
            
            if behavioral_metrics and track_id in behavioral_metrics:
                metrics = behavioral_metrics[track_id]
                risk_level = metrics.engagement_risk_level
                color = self.colors.get(risk_level, self.colors["default"])
            
            # Draw bounding box
            thickness = 3 if risk_level == "high" else 2
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            
            # Draw student ID and basic info
            label = f"ID {track_id}"
            # Append identity name if available
            identity_name = student.get("identity_name")
            identity_score = student.get("identity_score")
            if identity_name:
                if identity_score is not None:
                    label += f" | {identity_name} ({identity_score:.2f})"
                else:
                    label += f" | {identity_name}"
            if student.get("head_direction"):
                label += f" | {student['head_direction']}"
            
            # Background for text
            (text_width, text_height), baseline = cv2.getTextSize(
                label, self.font, self.font_scale_medium, self.font_thickness
            )
            cv2.rectangle(frame, (x1, y1 - text_height - 10), 
                         (x1 + text_width + 10, y1), color, -1)
            
            # Text
            cv2.putText(frame, label, (x1 + 5, y1 - 5), self.font, 
                       self.font_scale_medium, (255, 255, 255), self.font_thickness)
            
            # Draw risk indicator if available
            if behavioral_metrics and track_id in behavioral_metrics:
                metrics = behavioral_metrics[track_id]
                self._draw_risk_indicator(frame, x1, y2, metrics)
    
    def _draw_risk_indicator(self, frame, x, y, metrics):
        """Draw detailed risk indicator below student box."""
        indicators = []
        
        # Attention indicator
        attention_color = self._get_gradient_color(metrics.attention_score)
        indicators.append(("ATT", attention_color, f"{metrics.attention_score:.0%}"))
        
        # Phone risk indicator
        if metrics.phone_risk_score > 0.2:
            phone_color = self._get_gradient_color(1.0 - metrics.phone_risk_score)
            indicators.append(("PHN", phone_color, f"{metrics.phone_risk_score:.0%}"))
        
        # Draw indicators
        offset_x = 0
        for label, color, value in indicators:
            # Background
            cv2.rectangle(frame, (x + offset_x, y + 5), 
                         (x + offset_x + 80, y + 25), color, -1)
            
            # Border
            cv2.rectangle(frame, (x + offset_x, y + 5), 
                         (x + offset_x + 80, y + 25), (0, 0, 0), 1)
            
            # Text
            text = f"{label}:{value}"
            cv2.putText(frame, text, (x + offset_x + 5, y + 20), 
                       self.font, self.font_scale_small, (255, 255, 255), 1)
            
            offset_x += 85
    
    def _get_gradient_color(self, score):
        """Get color based on score (0-1), green->yellow->red."""
        if score > 0.7:
            return (0, 255, 0)  # Green
        elif score > 0.4:
            return (0, 200, 255)  # Yellow-orange
        else:
            return (0, 0, 255)  # Red
    
    def draw_statistics_panel(self, frame, summary: dict, metrics_summary: Optional[dict] = None):
        """
        Draw statistics panel in top-right corner.
        
        Args:
            frame: Video frame
            summary: Frame signal summary
            metrics_summary: Temporal aggregation summary (optional)
        """
        height, width = frame.shape[:2]
        panel_width = 300
        panel_x = width - panel_width - 10
        panel_y = 10
        
        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (panel_x, panel_y), 
                     (panel_x + panel_width, panel_y + 180), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        
        # Border
        cv2.rectangle(frame, (panel_x, panel_y), 
                     (panel_x + panel_width, panel_y + 180), (255, 255, 255), 2)
        
        # Title
        cv2.putText(frame, "SESSION STATISTICS", (panel_x + 10, panel_y + 25), 
                   self.font, self.font_scale_medium, (255, 255, 255), self.font_thickness_bold)
        
        # Statistics
        y_offset = 50
        stats_lines = [
            f"Students: {summary.get('total_students', 0)}",
            f"With Phones: {summary.get('students_with_phones', 0)}",
            f"Looking Away: {summary.get('students_looking_away', 0)}",
            f"Distraction: {summary.get('distraction_rate', 0):.0%}"
        ]
        
        if metrics_summary:
            stats_lines.append("")
            stats_lines.append(f"Avg Risk: {metrics_summary.get('avg_engagement_risk', 0):.0%}")
            stats_lines.append(f"High Risk: {metrics_summary.get('high_risk_students', 0)}")
        
        for line in stats_lines:
            if line:  # Skip empty lines for spacing
                cv2.putText(frame, line, (panel_x + 10, panel_y + y_offset), 
                           self.font, self.font_scale_small, (255, 255, 255), 1)
            y_offset += 20
    
    def add_alert(self, timestamp: float, alert):
        """Add an alert to the display buffer."""
        self.active_alerts.append({
            "timestamp": timestamp,
            "alert": alert
        })
    
    def draw_alerts(self, frame, current_timestamp: float):
        """
        Draw active alerts on screen.
        
        Args:
            frame: Video frame
            current_timestamp: Current elapsed time
        """
        # Remove expired alerts
        self.active_alerts = [
            a for a in self.active_alerts 
            if current_timestamp - a["timestamp"] < self.alert_duration
        ]
        
        if not self.active_alerts:
            return
        
        height, width = frame.shape[:2]
        alert_y = height - 150
        
        # Draw alert panel
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, alert_y), (width - 10, height - 10), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Border
        cv2.rectangle(frame, (10, alert_y), (width - 10, height - 10), (0, 0, 255), 2)
        
        # Title
        cv2.putText(frame, "🚨 ACTIVE ALERTS", (20, alert_y + 25), 
                   self.font, self.font_scale_medium, (255, 255, 255), self.font_thickness_bold)
        
        # Draw alerts (show up to 3 most recent)
        y_offset = 50
        for alert_data in self.active_alerts[-3:]:
            alert = alert_data["alert"]
            color = self.alert_colors.get(alert.alert_level.value, (255, 255, 255))
            
            # Alert message
            msg = f"Student #{alert.track_id}: {alert.message[:60]}"
            cv2.putText(frame, msg, (20, alert_y + y_offset), 
                       self.font, self.font_scale_small, color, 1)
            
            y_offset += 20
    
    def draw_head_direction_indicator(self, frame, bbox, direction):
        """
        Draw arrow indicating head direction.
        
        Args:
            frame: Video frame
            bbox: Bounding box [x1, y1, x2, y2]
            direction: Head direction string
        """
        x1, y1, x2, y2 = map(int, bbox)
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        
        # Arrow endpoints based on direction
        arrow_length = 40
        arrows = {
            "forward": (center_x, center_y - arrow_length),
            "left": (center_x - arrow_length, center_y),
            "right": (center_x + arrow_length, center_y),
            "up": (center_x, center_y - arrow_length),
            "down": (center_x, center_y + arrow_length)
        }
        
        if direction in arrows:
            end_point = arrows[direction]
            cv2.arrowedLine(frame, (center_x, center_y), end_point, 
                          (255, 255, 0), 2, tipLength=0.3)
    
    def draw_fps(self, frame, fps: float):
        """Draw FPS counter."""
        cv2.rectangle(frame, (0, 0), (100, 35), (0, 0, 0), -1)
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 25), 
                   self.font, self.font_scale_medium, (0, 255, 0), self.font_thickness)
    
    def draw_timestamp(self, frame, timestamp: float):
        """Draw elapsed time."""
        height = frame.shape[0]
        time_str = f"Time: {timestamp:.1f}s"
        
        (text_width, text_height), _ = cv2.getTextSize(
            time_str, self.font, self.font_scale_medium, self.font_thickness
        )
        
        cv2.rectangle(frame, (0, height - 35), (text_width + 20, height), (0, 0, 0), -1)
        cv2.putText(frame, time_str, (10, height - 10), 
                   self.font, self.font_scale_medium, (255, 255, 255), self.font_thickness)
    
    def render_full_overlay(self, frame, students, frame_summary, timestamp, fps,
                           behavioral_metrics=None, metrics_summary=None, 
                           show_head_arrows=False):
        """
        Render complete visual overlay on frame.
        
        Args:
            frame: Video frame
            students: List of student dicts
            frame_summary: Frame signal summary
            timestamp: Elapsed time
            fps: Current FPS
            behavioral_metrics: Dict of behavioral metrics (optional)
            metrics_summary: Temporal aggregation summary (optional)
            show_head_arrows: Whether to show head direction arrows
        
        Returns:
            Annotated frame
        """
        # Draw student boxes with risk coloring
        self.draw_student_boxes(frame, students, behavioral_metrics)
        
        # Draw head direction arrows if requested
        if show_head_arrows:
            for student in students:
                if student.get("head_direction") not in ["unknown", "no_face"]:
                    self.draw_head_direction_indicator(
                        frame, student["bbox"], student["head_direction"]
                    )
        
        # Draw statistics panel
        self.draw_statistics_panel(frame, frame_summary, metrics_summary)
        
        # Draw active alerts
        self.draw_alerts(frame, timestamp)
        
        # Draw FPS and timestamp
        self.draw_fps(frame, fps)
        self.draw_timestamp(frame, timestamp)
        
        return frame
