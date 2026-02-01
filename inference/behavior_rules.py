"""Rule-based inference engine for student behavior analysis."""
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of behavioral alerts."""
    SUSTAINED_INATTENTION = "sustained_inattention"
    PHONE_USAGE = "phone_usage"
    PHONE_USAGE_INCREASING = "phone_usage_increasing"
    COMBINED_DISTRACTION = "combined_distraction"
    HIGH_RISK_BEHAVIOR = "high_risk_behavior"
    ATTENTION_DROP = "attention_drop"
    QUALITY_WARNING = "quality_warning"


@dataclass
class BehaviorAlert:
    """Represents a behavioral alert or warning."""
    track_id: int
    timestamp: float
    alert_type: AlertType
    alert_level: AlertLevel
    message: str
    metrics: dict  # Supporting metrics for this alert
    recommended_action: str
    identity_name: Optional[str] = None  # Recognized identity
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "track_id": self.track_id,
            "timestamp": self.timestamp,
            "alert_type": self.alert_type.value,
            "alert_level": self.alert_level.value,
            "message": self.message,
            "metrics": self.metrics,
            "recommended_action": self.recommended_action,
            "identity_name": self.identity_name
        }


class BehaviorRuleEngine:
    """Rule-based inference engine for analyzing student behavior."""
    
    def __init__(self, config: Optional[dict] = None):
        """
        Initialize the rule engine with configurable thresholds.
        
        Args:
            config (dict): Configuration with threshold values
        """
        # Default thresholds - can be overridden
        self.config = config or {}
        self.attention_threshold = self.config.get("attention_threshold", 0.5)
        self.phone_risk_threshold = self.config.get("phone_risk_threshold", 0.4)
        self.engagement_risk_threshold = self.config.get("engagement_risk_threshold", 0.6)
        self.min_samples_for_alert = self.config.get("min_samples_for_alert", 5)
        
        # History for tracking changes
        self.previous_metrics: Dict[int, any] = {}
    
    def evaluate(self, behavioral_metrics) -> List[BehaviorAlert]:
        """
        Evaluate behavioral metrics and generate alerts.
        
        Args:
            behavioral_metrics: BehavioralMetrics object from TemporalAggregator
        
        Returns:
            List of BehaviorAlert objects
        """
        alerts = []
        track_id = behavioral_metrics.track_id
        timestamp = behavioral_metrics.timestamp
        
        # Skip evaluation if data quality is too low
        if behavioral_metrics.data_quality == "low" and behavioral_metrics.sample_count < 3:
            if behavioral_metrics.sample_count > 0:
                student_ref = behavioral_metrics.identity_name or f"Student #{track_id}"
                alerts.append(BehaviorAlert(
                    track_id=track_id,
                    timestamp=timestamp,
                    alert_type=AlertType.QUALITY_WARNING,
                    alert_level=AlertLevel.INFO,
                    message=f"Low data quality for {student_ref}",
                    metrics={"sample_count": behavioral_metrics.sample_count},
                    recommended_action="Wait for more samples before making decisions",
                    identity_name=behavioral_metrics.identity_name
                ))
            return alerts
        
        # Rule 1: High engagement risk (combined factors)
        if behavioral_metrics.engagement_risk_level == "high":
            alerts.append(self._rule_high_risk(behavioral_metrics))
        
        # Rule 2: Sustained inattention
        if (behavioral_metrics.attention_score < self.attention_threshold and
            behavioral_metrics.sample_count >= self.min_samples_for_alert):
            alerts.append(self._rule_sustained_inattention(behavioral_metrics))
        
        # Rule 3: Phone usage detection
        if behavioral_metrics.phone_risk_score > self.phone_risk_threshold:
            alerts.append(self._rule_phone_usage(behavioral_metrics))
        
        # Rule 4: Increasing phone usage trend
        if (behavioral_metrics.phone_trend == "increasing" and
            behavioral_metrics.phone_detection_rate > 0.2):
            alerts.append(self._rule_phone_increasing(behavioral_metrics))
        
        # Rule 5: Combined distraction (phone + looking away)
        if (behavioral_metrics.phone_risk_score > 0.3 and
            behavioral_metrics.looking_away_rate > 0.6):
            alerts.append(self._rule_combined_distraction(behavioral_metrics))
        
        # Rule 6: Sudden attention drop (compared to previous)
        attention_drop_alert = self._rule_attention_drop(behavioral_metrics)
        if attention_drop_alert:
            alerts.append(attention_drop_alert)
        
        # Update history
        self.previous_metrics[track_id] = behavioral_metrics
        
        return alerts
    
    def _rule_high_risk(self, metrics) -> BehaviorAlert:
        """Rule for high overall engagement risk."""
        student_ref = metrics.identity_name or f"Student #{metrics.track_id}"
        return BehaviorAlert(
            track_id=metrics.track_id,
            timestamp=metrics.timestamp,
            alert_type=AlertType.HIGH_RISK_BEHAVIOR,
            alert_level=AlertLevel.CRITICAL,
            message=f"{student_ref} shows high-risk behavior pattern",
            metrics={
                "engagement_risk_score": metrics.engagement_risk_score,
                "primary_behavior": metrics.primary_behavior,
                "attention_score": metrics.attention_score,
                "phone_risk_score": metrics.phone_risk_score
            },
            recommended_action="Immediate intervention recommended - check on student",
            identity_name=metrics.identity_name
        )
    
    def _rule_sustained_inattention(self, metrics) -> BehaviorAlert:
        """Rule for sustained inattention."""
        severity = AlertLevel.CRITICAL if metrics.attention_score < 0.3 else AlertLevel.WARNING
        student_ref = metrics.identity_name or f"Student #{metrics.track_id}"
        
        return BehaviorAlert(
            track_id=metrics.track_id,
            timestamp=metrics.timestamp,
            alert_type=AlertType.SUSTAINED_INATTENTION,
            alert_level=severity,
            message=f"{student_ref} showing sustained inattention ({metrics.attention_score:.1%})",
            metrics={
                "attention_score": metrics.attention_score,
                "looking_away_rate": metrics.looking_away_rate,
                "duration": metrics.observation_duration,
                "sample_count": metrics.sample_count
            },
            recommended_action="Monitor closely or provide gentle reminder to focus",
            identity_name=metrics.identity_name
        )
    
    def _rule_phone_usage(self, metrics) -> BehaviorAlert:
        """Rule for phone usage detection."""
        severity = AlertLevel.CRITICAL if metrics.phone_risk_score > 0.6 else AlertLevel.WARNING
        student_ref = metrics.identity_name or f"Student #{metrics.track_id}"
        
        return BehaviorAlert(
            track_id=metrics.track_id,
            timestamp=metrics.timestamp,
            alert_type=AlertType.PHONE_USAGE,
            alert_level=severity,
            message=f"{student_ref} likely using phone (risk: {metrics.phone_risk_score:.1%})",
            metrics={
                "phone_risk_score": metrics.phone_risk_score,
                "phone_detection_rate": metrics.phone_detection_rate,
                "phone_trend": metrics.phone_trend
            },
            recommended_action="Politely ask student to put away phone",
            identity_name=metrics.identity_name
        )
    
    def _rule_phone_increasing(self, metrics) -> BehaviorAlert:
        """Rule for increasing phone usage trend."""
        student_ref = metrics.identity_name or f"Student #{metrics.track_id}"
        return BehaviorAlert(
            track_id=metrics.track_id,
            timestamp=metrics.timestamp,
            alert_type=AlertType.PHONE_USAGE_INCREASING,
            alert_level=AlertLevel.WARNING,
            message=f"{student_ref} phone usage trend is increasing",
            metrics={
                "phone_trend": metrics.phone_trend,
                "phone_detection_rate": metrics.phone_detection_rate,
                "phone_risk_score": metrics.phone_risk_score
            },
            recommended_action="Watch closely - may need intervention soon",
            identity_name=metrics.identity_name
        )
    
    def _rule_combined_distraction(self, metrics) -> BehaviorAlert:
        """Rule for combined phone usage and looking away."""
        student_ref = metrics.identity_name or f"Student #{metrics.track_id}"
        return BehaviorAlert(
            track_id=metrics.track_id,
            timestamp=metrics.timestamp,
            alert_type=AlertType.COMBINED_DISTRACTION,
            alert_level=AlertLevel.CRITICAL,
            message=f"{student_ref} showing combined distraction (phone + looking away)",
            metrics={
                "phone_risk_score": metrics.phone_risk_score,
                "looking_away_rate": metrics.looking_away_rate,
                "attention_score": metrics.attention_score
            },
            recommended_action="Immediate intervention - student is significantly distracted",
            identity_name=metrics.identity_name
        )
    
    def _rule_attention_drop(self, metrics) -> Optional[BehaviorAlert]:
        """Rule for sudden drop in attention."""
        if metrics.track_id not in self.previous_metrics:
            return None
        
        prev = self.previous_metrics[metrics.track_id]
        attention_change = metrics.attention_score - prev.attention_score
        
        # Alert if attention dropped significantly (>30% drop)
        if attention_change < -0.3 and metrics.sample_count >= 5:
            student_ref = metrics.identity_name or f"Student #{metrics.track_id}"
            return BehaviorAlert(
                track_id=metrics.track_id,
                timestamp=metrics.timestamp,
                alert_type=AlertType.ATTENTION_DROP,
                alert_level=AlertLevel.WARNING,
                message=f"{student_ref} attention dropped significantly",
                metrics={
                    "previous_attention": prev.attention_score,
                    "current_attention": metrics.attention_score,
                    "change": attention_change
                },
                recommended_action="Check if student needs help or is confused",
                identity_name=metrics.identity_name
            )
        
        return None
    
    def evaluate_all(self, all_behavioral_metrics: Dict[int, any]) -> Dict[int, List[BehaviorAlert]]:
        """
        Evaluate all students and generate alerts.
        
        Args:
            all_behavioral_metrics: Dict of track_id -> BehavioralMetrics
        
        Returns:
            Dict of track_id -> List[BehaviorAlert]
        """
        all_alerts = {}
        for track_id, metrics in all_behavioral_metrics.items():
            alerts = self.evaluate(metrics)
            if alerts:
                all_alerts[track_id] = alerts
        
        return all_alerts
    
    def get_critical_alerts(self, all_alerts: Dict[int, List[BehaviorAlert]]) -> List[BehaviorAlert]:
        """Get only critical alerts from all alerts."""
        critical = []
        for alerts in all_alerts.values():
            critical.extend([a for a in alerts if a.alert_level == AlertLevel.CRITICAL])
        return critical
    
    def get_alerts_by_type(self, all_alerts: Dict[int, List[BehaviorAlert]], 
                          alert_type: AlertType) -> List[BehaviorAlert]:
        """Get alerts of a specific type."""
        filtered = []
        for alerts in all_alerts.values():
            filtered.extend([a for a in alerts if a.alert_type == alert_type])
        return filtered
    
    def get_summary(self, all_alerts: Dict[int, List[BehaviorAlert]]) -> dict:
        """Get summary statistics of all alerts."""
        total_alerts = sum(len(alerts) for alerts in all_alerts.values())
        critical_count = len(self.get_critical_alerts(all_alerts))
        warning_count = sum(
            len([a for a in alerts if a.alert_level == AlertLevel.WARNING])
            for alerts in all_alerts.values()
        )
        students_with_alerts = len(all_alerts)
        
        return {
            "total_alerts": total_alerts,
            "critical_alerts": critical_count,
            "warning_alerts": warning_count,
            "students_with_alerts": students_with_alerts,
            "students_needing_intervention": critical_count
        }
