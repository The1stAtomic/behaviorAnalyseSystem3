"""Temporal aggregator for converting feature buffer statistics to behavioral metrics."""
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class BehavioralMetrics:
    """Aggregated behavioral metrics for a student suitable for rule-based inference."""
    track_id: int
    timestamp: float
    
    # Temporal metrics
    observation_duration: float  # How long we've been observing this student
    sample_count: int  # Number of features in the window
    
    # Attention metrics
    attention_score: float  # 0.0-1.0, higher = more attentive (looking forward)
    looking_away_rate: float  # 0.0-1.0, rate of non-forward head directions
    direction_stability: float  # 0.0-1.0, consistency in head direction (low = changing a lot)
    
    # Phone metrics
    phone_risk_score: float  # 0.0-1.0, likelihood of phone usage
    phone_detection_rate: float  # Rate of phone detections
    phone_trend: str  # "increasing", "decreasing", "stable"
    
    # Overall metrics
    engagement_risk_level: str  # "low", "medium", "high"
    engagement_risk_score: float  # 0.0-1.0
    primary_behavior: str  # "attentive", "distracted_phone", "distracted_other"
    
    # Confidence metrics
    avg_confidence: float  # Detection confidence
    data_quality: str  # "low", "medium", "high"
    
    # Optional identity
    identity_name: Optional[str] = None  # Recognized identity name
    
    def to_dict(self):
        """Convert to dictionary for logging or downstream processing."""
        return {
            "track_id": self.track_id,
            "timestamp": self.timestamp,
            "identity_name": self.identity_name,
            "observation_duration": round(self.observation_duration, 2),
            "sample_count": self.sample_count,
            "attention_score": round(self.attention_score, 3),
            "looking_away_rate": round(self.looking_away_rate, 3),
            "direction_stability": round(self.direction_stability, 3),
            "phone_risk_score": round(self.phone_risk_score, 3),
            "phone_detection_rate": round(self.phone_detection_rate, 3),
            "phone_trend": self.phone_trend,
            "engagement_risk_level": self.engagement_risk_level,
            "engagement_risk_score": round(self.engagement_risk_score, 3),
            "primary_behavior": self.primary_behavior,
            "avg_confidence": round(self.avg_confidence, 3),
            "data_quality": self.data_quality
        }


class TemporalAggregator:
    """Aggregates temporal data from feature buffers into behavioral metrics."""
    
    def __init__(self):
        self.phone_history: Dict[int, List[float]] = {}  # track_id -> phone detection history
    
    def cleanup_track_history(self, track_id: int):
        """Clean up phone history for a track that's no longer active."""
        if track_id in self.phone_history:
            del self.phone_history[track_id]
    
    def aggregate(self, track_id: int, current_timestamp: float, buffer_stats: dict, 
                 raw_phone_risk: float = None) -> BehavioralMetrics:
        """
        Aggregate feature buffer statistics into behavioral metrics.
        
        Args:
            track_id (int): Student's track ID
            current_timestamp (float): Current time
            buffer_stats (dict): Statistics from StudentFeatureBuffer.get_statistics()
            raw_phone_risk (float): Direct phone risk from detection (0.0-1.0), optional
            track_id (int): Student's track ID
            current_timestamp (float): Current time
            buffer_stats (dict): Statistics from StudentFeatureBuffer.get_statistics()
        
        Returns:
            BehavioralMetrics: Aggregated metrics suitable for rule-based inference
        """
        
        # Extract base statistics
        sample_count = buffer_stats.get("feature_count", 0)
        observation_duration = buffer_stats.get("time_span", 0.0)
        avg_confidence = buffer_stats.get("avg_confidence", 0.0)
        phone_detection_rate = buffer_stats.get("phone_detection_rate", 0.0)
        head_directions = buffer_stats.get("head_direction_distribution", {})
        identity_name = buffer_stats.get("identity_name")
        
        # Handle case with no data
        if sample_count == 0:
            return self._create_empty_metrics(track_id, current_timestamp)
        
        # Calculate attention score (most recent direction for instant response)
        most_recent_direction = buffer_stats.get("most_recent_direction")
        forward_rate = head_directions.get("forward", 0.0)
        
        # Aggressive: if most recent frame is forward, instant 1.0 attention
        if most_recent_direction == "forward":
            attention_score = 1.0
        else:
            attention_score = 0.0
        
        looking_away_rate = 1.0 - attention_score
        
        # Calculate direction stability (how consistent is behavior)
        if head_directions:
            max_direction_rate = max(head_directions.values())
            direction_stability = max_direction_rate  # Higher = more stable/consistent
        else:
            direction_stability = 0.5
        
        # Calculate phone risk score
        # Use raw phone risk if provided, otherwise use buffered detection rate
        if raw_phone_risk is not None:
            phone_risk_score = raw_phone_risk
            phone_trend = self._calculate_phone_trend(track_id, raw_phone_risk)
        else:
            phone_risk_score = self._calculate_phone_risk(track_id, phone_detection_rate)
            phone_trend = self._calculate_phone_trend(track_id, phone_detection_rate)
        
        # Determine primary behavior
        primary_behavior = self._determine_primary_behavior(
            attention_score, phone_detection_rate, head_directions
        )
        
        # Calculate overall engagement risk
        engagement_risk_score = self._calculate_engagement_risk(
            attention_score, phone_risk_score, looking_away_rate
        )
        
        engagement_risk_level = self._classify_risk_level(engagement_risk_score)
        
        # Assess data quality
        data_quality = self._assess_data_quality(sample_count, avg_confidence)
        
        metrics = BehavioralMetrics(
            track_id=track_id,
            timestamp=current_timestamp,
            identity_name=identity_name,
            observation_duration=observation_duration,
            sample_count=sample_count,
            attention_score=attention_score,
            looking_away_rate=looking_away_rate,
            direction_stability=direction_stability,
            phone_risk_score=phone_risk_score,
            phone_detection_rate=phone_detection_rate,
            phone_trend=phone_trend,
            engagement_risk_level=engagement_risk_level,
            engagement_risk_score=engagement_risk_score,
            primary_behavior=primary_behavior,
            avg_confidence=avg_confidence,
            data_quality=data_quality
        )
        
        return metrics
    
    def _calculate_phone_risk(self, track_id: int, current_phone_rate: float) -> float:
        """
        Calculate phone risk score based on detection rate and history.
        NOTE: This is only used as fallback when raw_phone_risk is not provided.
        
        Returns:
            float: 0.0-1.0 risk score
        """
        # Directly use the phone detection rate as risk
        return min(1.0, max(0.0, current_phone_rate))
    
    def _calculate_phone_trend(self, track_id: int, current_phone_rate: float) -> str:
        """
        Determine if phone detection is increasing, decreasing, or stable.
        
        Returns:
            str: "increasing", "decreasing", or "stable"
        """
        if track_id not in self.phone_history or len(self.phone_history[track_id]) < 2:
            return "stable"
        
        history = self.phone_history[track_id]
        if len(history) >= 3:
            recent_avg = sum(history[-3:]) / 3
            older_avg = sum(history[:-3]) / len(history[:-3]) if len(history) > 3 else history[0]
        else:
            recent_avg = history[-1]
            older_avg = history[0]
        
        # Check for trend with some tolerance
        threshold = 0.1
        if recent_avg > older_avg + threshold:
            return "increasing"
        elif recent_avg < older_avg - threshold:
            return "decreasing"
        else:
            return "stable"
    
    def _determine_primary_behavior(self, attention_score: float, phone_rate: float, 
                                    head_directions: dict) -> str:
        """Determine the primary behavior pattern."""
        if phone_rate > 0.3:  # High phone detection
            return "distracted_phone"
        elif attention_score < 0.5:  # Low attention
            return "distracted_other"
        else:
            return "attentive"
    
    def _calculate_engagement_risk(self, attention_score: float, phone_risk: float, 
                                   looking_away_rate: float) -> float:
        """
        Calculate overall engagement risk combining multiple factors.
        
        Returns:
            float: 0.0-1.0, higher = more risky
        """
        # Risk increases with: low attention, high phone risk, looking away
        # Risk is a weighted combination
        risk = (
            (1.0 - attention_score) * 0.4 +  # Attention (40% weight)
            phone_risk * 0.35 +                # Phone risk (35% weight)
            looking_away_rate * 0.25           # Looking away (25% weight)
        )
        return min(1.0, max(0.0, risk))  # Clamp to 0-1
    
    def _classify_risk_level(self, risk_score: float) -> str:
        """Classify risk score into categories."""
        if risk_score < 0.33:
            return "low"
        elif risk_score < 0.67:
            return "medium"
        else:
            return "high"
    
    def _assess_data_quality(self, sample_count: int, avg_confidence: float) -> str:
        """Assess quality of the data underlying these metrics."""
        if sample_count < 5 or avg_confidence < 0.6:
            return "low"
        elif sample_count < 20 or avg_confidence < 0.75:
            return "medium"
        else:
            return "high"
    
    def _create_empty_metrics(self, track_id: int, current_timestamp: float) -> BehavioralMetrics:
        """Create empty/default metrics when no data available."""
        return BehavioralMetrics(
            track_id=track_id,
            timestamp=current_timestamp,
            observation_duration=0.0,
            sample_count=0,
            attention_score=0.5,
            looking_away_rate=0.5,
            direction_stability=0.0,
            phone_risk_score=0.0,
            phone_detection_rate=0.0,
            phone_trend="stable",
            engagement_risk_level="low",
            engagement_risk_score=0.5,
            primary_behavior="unknown",
            avg_confidence=0.0,
            data_quality="low"
        )


class TemporalAggregationPipeline:
    """Convenience wrapper for aggregating all students at once."""
    
    def __init__(self):
        self.aggregator = TemporalAggregator()
    
    def aggregate_all(self, current_timestamp: float, 
                     all_buffer_stats: Dict[int, dict],
                     raw_phone_risk: Dict[int, float] = None) -> Dict[int, BehavioralMetrics]:
        """
        Aggregate metrics for all students.
        
        Args:
            current_timestamp (float): Current time
            all_buffer_stats (dict): Output from FeatureBuffer.get_all_statistics()
            raw_phone_risk (dict): Direct phone risk scores from detection (optional)
        
        Returns:
            dict: track_id -> BehavioralMetrics
        """
        if raw_phone_risk is None:
            raw_phone_risk = {}
            
        metrics_dict = {}
        for track_id, stats in all_buffer_stats.items():
            metrics = self.aggregator.aggregate(track_id, current_timestamp, stats, 
                                               raw_phone_risk.get(track_id))
            metrics_dict[track_id] = metrics
        
        return metrics_dict
    
    def get_high_risk_students(self, metrics_dict: Dict[int, BehavioralMetrics]) -> List[int]:
        """Get list of track IDs with high engagement risk."""
        return [
            track_id for track_id, metrics in metrics_dict.items()
            if metrics.engagement_risk_level == "high"
        ]
    
    def get_metrics_summary(self, metrics_dict: Dict[int, BehavioralMetrics]) -> dict:
        """Get summary statistics across all students."""
        if not metrics_dict:
            return {}
        
        all_metrics = list(metrics_dict.values())
        avg_engagement_risk = sum(m.engagement_risk_score for m in all_metrics) / len(all_metrics)
        high_risk_count = sum(1 for m in all_metrics if m.engagement_risk_level == "high")
        
        return {
            "total_students": len(all_metrics),
            "avg_engagement_risk": round(avg_engagement_risk, 3),
            "high_risk_students": high_risk_count,
            "avg_attention": round(sum(m.attention_score for m in all_metrics) / len(all_metrics), 3),
            "avg_phone_risk": round(sum(m.phone_risk_score for m in all_metrics) / len(all_metrics), 3)
        }
