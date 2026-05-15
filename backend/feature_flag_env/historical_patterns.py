"""
feature_flag_env/historical_patterns.py

System for tracking historical deployment patterns and computing risk scores.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

@dataclass
class DeploymentPattern:
    """Represents a specific known failure pattern."""
    pattern_id: str
    description: str
    critical_rollout_threshold: float
    expected_error_spike: float
    risk_weight: float = 1.0

class PatternMemory:
    """Stores past deployment outcomes to identify recurring failures."""
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.history: List[Dict[str, Any]] = []

    def record_deployment(self, metrics: Dict[str, Any], outcome: str):
        """Add a deployment result to history."""
        self.history.append({
            "metrics": metrics,
            "outcome": outcome
        })
        if len(self.history) > self.capacity:
            self.history.pop(0)

    def get_avg_failure_rollout(self) -> Optional[float]:
        """Compute the average rollout percentage where failures occur."""
        failures = [h["metrics"]["max_rollout"] for h in self.history if h["outcome"] == "failure"]
        if not failures:
            return None
        return sum(failures) / len(failures)


class CustomerProfile:
    """Encapsulates customer-specific risk traits and historical data."""
    def __init__(self, customer_id: str, 
                 risk_tolerance: float = 0.5,
                 risk_weights: Optional[Dict[str, float]] = None,
                 historical_patterns: Optional[List[DeploymentPattern]] = None):
        self.customer_id = customer_id
        self.risk_tolerance = risk_tolerance # 0 (risk-averse) to 1 (risk-tolerant)
        self.risk_weights = risk_weights or {}
        self.memory = PatternMemory()
        self.known_patterns = historical_patterns or []

    def add_pattern(self, pattern: DeploymentPattern):
        self.known_patterns.append(pattern)


class PatternAnalyzer:
    """Analyzes memory and patterns to compute real-time risk scores."""
    def __init__(self, profile: CustomerProfile):
        self.profile = profile

    def compute_risk(self, current_rollout: float, current_error_rate: float) -> float:
        """
        Compute a risk score [0.0, 1.0] based on patterns and current state.
        """
        risk = float(0.0)
        
        # 1. Check against known patterns
        for pattern in self.profile.known_patterns:
            if current_rollout >= pattern.critical_rollout_threshold:
                # Proximity to threshold increases risk
                dist = abs(current_rollout - pattern.critical_rollout_threshold)
                if dist < 10.0:
                    risk += (1.0 - (dist / 10.0)) * pattern.risk_weight

        # 2. Check historical failure trends
        avg_fail_rollout = self.profile.memory.get_avg_failure_rollout()
        if avg_fail_rollout is not None:
            if current_rollout >= (avg_fail_rollout - 5.0):
                risk += 0.3 # Historical warning zone

        # 3. Factor in error rate momentum
        if current_error_rate > 0.03:
            risk += 0.2
        
        # 4. Sensitivity based on customer risk tolerance
        risk_adjustment = (1.0 - self.profile.risk_tolerance)
        risk *= (1.0 + risk_adjustment)

        return min(1.0, risk)
