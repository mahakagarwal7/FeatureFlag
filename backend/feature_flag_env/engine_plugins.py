"""
feature_flag_env/engine_plugins.py

Advanced plug-ins for the simulator:
- ChaosEngine: Inject randomized performance degradation.
- ApprovalWorkflow: Manage Human-in-the-Loop (HITL) blocking approvals.
"""

import random
from typing import Dict, Any, Optional, List
from datetime import datetime
from feature_flag_env.models import FeatureFlagAction, FeatureFlagState

class ChaosEngine:
    """
    Simulates real-world incidents and performance degradation.
    Pluggable into the environment step loop.
    """
    def __init__(self, incident_rate: float = 0.05, intensity_range: tuple = (0.1, 0.5)):
        self.incident_rate = incident_rate
        self.intensity_range = intensity_range
        self.active_incident: Optional[Dict[str, Any]] = None
        self.cooldown: int = 0

    def step(self) -> Optional[Dict[str, Any]]:
        """Process one tick of chaos."""
        incident = self.active_incident
        if incident:
            incident["duration"] = int(incident["duration"]) - 1
            if int(incident["duration"]) <= 0:
                self.active_incident = None
                self.cooldown = 5  # No new incidents for 5 steps
            return incident

        if self.cooldown > 0:
            self.cooldown -= 1
            return None

        if random.random() < self.incident_rate:
            self.active_incident = {
                "type": random.choice(["latency_spike", "error_burst", "api_degradation"]),
                "intensity": random.uniform(*self.intensity_range),
                "duration": random.randint(2, 5)
            }
            return self.active_incident
        
        return None

    def reset(self):
        self.active_incident = None
        self.cooldown = 0


class ApprovalWorkflow:
    """
    Manages high-risk phase transition approvals (HITL).
    """
    def __init__(self):
        self.status: str = "NONE"  # NONE, PENDING, APPROVED, REJECTED
        self.blocking_phase: Optional[str] = None
        self.history: List[Dict[str, Any]] = []

    def request_approval(self, phase_name: str, details: str):
        """Trigger an approval request."""
        self.status = "PENDING"
        self.blocking_phase = phase_name
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "phase": phase_name,
            "details": details,
            "status": "PENDING"
        })

    def process_mock_approval(self, confidence_score: float):
        """Simulate a human/stakeholder response based on confidence."""
        if self.status != "PENDING":
            return

        # Simple logic: if confidence is high, approve; else maybe reject or stay pending
        if confidence_score > 0.8:
            self.status = "APPROVED"
        elif confidence_score < 0.3:
            self.status = "REJECTED"
        
        if self.status != "PENDING":
            self.history[-1]["status"] = self.status
            self.history[-1]["responded_at"] = datetime.now().isoformat()

    def reset(self):
        self.status = "NONE"
        self.blocking_phase = None
        self.history = []

    def get_status(self) -> str:
        return self.status
