"""
feature_flag_env/anomaly_detection.py

Side-car module for real-time anomaly detection using rolling window base-lines.
"""

import math
from typing import Dict, Any, List, Optional
from collections import deque

class AnomalyDetector:
    """
    Detects behavioral anomalies in environment metrics using Z-score logic.
    Maintains a rolling history to establish a dynamic baseline.
    """
    def __init__(self, window_size: int = 20, threshold: float = 3.0):
        self.window_size = window_size
        self.threshold = threshold # Z-score threshold for anomaly
        
        # Metric histories
        self.metrics_history: Dict[str, deque] = {
            "error_rate": deque(maxlen=window_size),
            "latency_p99_ms": deque(maxlen=window_size),
            "revenue_impact": deque(maxlen=window_size),
            "system_health_score": deque(maxlen=window_size)
        }

    def update_baselines(self, observation_data: Dict[str, Any]):
        """Record current metrics to the rolling window."""
        for key in self.metrics_history:
            if key in observation_data and observation_data[key] is not None:
                self.metrics_history[key].append(float(observation_data[key]))

    def detect(self, current_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute anomaly score and return structural metadata.
        Score is 0-1, where 1 is highly anomalous.
        """
        anomalies = []
        max_z = 0.0
        
        for key, history in self.metrics_history.items():
            if len(history) < 5: # Need minimum samples for stable baseline
                continue
            
            val = float(current_metrics.get(key, 0.0))
            
            # Compute mean and std
            history_list = list(history)
            mean = sum(history_list) / len(history_list)
            var = sum((float(x) - mean)**2 for x in history_list) / len(history_list)
            std = math.sqrt(var)
            
            # Handle stationary metrics (std=0 or very small)
            # If std is tiny, use a minimum epsilon (0.01) to ignore tiny jitters
            effective_std = max(std, 0.01)
                
            z_score = abs(val - mean) / effective_std
            if z_score > self.threshold:
                anomalies.append(key)
                max_z = max(max_z, z_score)

        # Map max Z-score to 0-1 range
        # Assume Z=3 is 0.5, Z=6+ is 1.0
        anomaly_score = 0.0
        if max_z > 0:
            anomaly_score = min(1.0, max_z / (self.threshold * 2))

        explanation = "Normal operation."
        if anomalies:
            explanation = f"Anomaly detected in: {', '.join(anomalies)}. Extreme Z-score: {float(max_z):.2f}"

        return {
            "anomaly_score": float(round(anomaly_score, 4)),
            "anomalies": anomalies,
            "explanation": explanation,
            "is_significant": bool(anomaly_score > 0.6)
        }

    def reset(self):
        """Clear history for new episode."""
        for history in self.metrics_history.values():
            history.clear()
