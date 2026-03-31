"""
feature_flag_env/server/simulation_engine.py

This is the "physics engine" that calculates what happens
when the agent takes an action.

It uses predefined mathematical formulas + controlled randomness
to simulate realistic system behavior.
"""

import numpy as np
from typing import Dict, Any, Optional


class FeatureFlagSimulator:
    """
    Simulates how a feature rollout affects system metrics.
    
    This class contains the "laws of physics" for our environment:
    - How errors scale with rollout percentage
    - How latency increases under load
    - How users adopt features over time
    - How revenue is generated
    """
    
    def __init__(
        self, 
        scenario_config: Dict[str, Any], 
        seed: Optional[int] = None
    ):
        """
        Initialize the simulator with a scenario configuration.
        
        Args:
            scenario_config: Dictionary with simulation parameters
            seed: Random seed for reproducibility (important for debugging!)
        """
        self.config = scenario_config
        self.rng = np.random.default_rng(seed)  
        
       
        self.current_rollout = 0.0
        self.error_rate = scenario_config.get("base_error_rate", 0.01)
        self.latency = 100.0  
        self.adoption_rate = 0.0
        self.revenue = 0.0
        self.consecutive_high_errors = 0
        
       
        self.last_error_rate = self.error_rate
        
    def step(self, target_rollout: float) -> Dict[str, Any]:
        """
        MAIN FUNCTION: Calculate new metrics after agent's action.
        
        This is called every time the agent takes a step.
        
        Args:
            target_rollout: The rollout percentage the agent wants (0-100)
            
        Returns:
            Dictionary with all updated metrics
        """
       
        self.error_rate = self._calculate_error_rate(target_rollout)
        
       
        self.latency = self._calculate_latency(target_rollout)
        
      
        self.adoption_rate = self._calculate_adoption(target_rollout)
        
       
        self.revenue = self._calculate_revenue(self.adoption_rate)
        
       
        health_score = self._calculate_health_score()
        
    
        total_users = self.config.get("total_users", 10000)
        active_users = int(self.adoption_rate * total_users)
        
       
        self.last_error_rate = self.error_rate
        self.current_rollout = target_rollout
        
      
        return {
            "error_rate": float(self.error_rate),
            "latency_p99_ms": float(self.latency),
            "user_adoption_rate": float(self.adoption_rate),
            "revenue_impact": float(self.revenue),
            "system_health_score": float(health_score),
            "active_users": int(active_users),
        }
    
    def _calculate_error_rate(self, rollout_pct: float) -> float:
        """
        Calculate how error rate changes with rollout.
        
        FORMULA: base_error × scale_factor + noise + incident_spikes + momentum
        
        Why this formula?
        - Errors tend to increase non-linearly as more users use the feature
        - Real systems have random noise (network issues, etc.)
        - Some rollout ranges are "danger zones" (incident zones)
        - Errors can have momentum (once high, they stay high briefly)
        """
       
        base = self.config.get("base_error_rate", 0.01)
        
       
        scale_factor = (rollout_pct / 100.0) ** 1.5
        deterministic_error = base * scale_factor
        
       
        noise_std = self.config.get("error_variance", 0.005)
        noise = self.rng.normal(0, noise_std)  
        
    
        incident_spike = 0.0
        incident_zones = self.config.get("incident_zones", [])
        
        for zone in incident_zones:
          
            if zone["min"] <= rollout_pct <= zone["max"]:
                if self.rng.random() < zone["probability"]:
                    incident_spike = zone["spike"]
                   
        momentum = 0.0
        if self.last_error_rate > 0.10:  
            momentum = 0.3 * self.last_error_rate  
        
       
        total_error = deterministic_error + noise + incident_spike + momentum
        
        
        return float(np.clip(total_error, 0.0, 1.0))
    
    def _calculate_latency(self, rollout_pct: float) -> float:
        """
        Calculate how latency changes with rollout.
        
        FORMULA: base_latency + load_factor + error_overhead + noise
        
        Why this formula?
        - More users = more server load = higher latency
        - High errors cause retries/timeouts = even higher latency
        - Real systems have random variance
        """
        base_latency = 100.0 
        
      
        load_factor_per_10pct = self.config.get("latency_per_10pct_rollout", 5.0)
        latency_from_load = (rollout_pct / 10.0) * load_factor_per_10pct
        
      
        error_overhead = self.error_rate * 200  
        
      
        noise = self.rng.normal(0, 5)  
        
       
        total_latency = base_latency + latency_from_load + error_overhead + noise
        
        
        return float(max(total_latency, 50.0))
    
    def _calculate_adoption(self, rollout_pct: float) -> float:
        """
        Calculate how user adoption changes.
        
        FORMULA: gradual_change(ideal_adoption, current_adoption, speed)
        
        Why gradual?
        - Users don't adopt features instantly
        - Adoption builds over time (user inertia)
        - High errors reduce adoption (users avoid buggy features)
        """

        quality_factor = 1 - (self.error_rate * 2)  
        ideal_adoption = (rollout_pct / 100.0) * quality_factor
        
       
        adoption_speed = self.config.get("adoption_speed", 0.1)
        
      
        new_adoption = self.adoption_rate + adoption_speed * (ideal_adoption - self.adoption_rate)
        
        
        return float(np.clip(new_adoption, 0.0, 1.0))
    
    def _calculate_revenue(self, adoption_rate: float) -> float:
        """
        Calculate revenue based on adoption.
        
        FORMULA: active_users × revenue_per_user
        
        Simple but realistic: more users adopting = more revenue
        """
        total_users = self.config.get("total_users", 10000)
        active_users = adoption_rate * total_users
        revenue_per_user = self.config.get("revenue_per_user", 0.10)  
        
        return float(active_users * revenue_per_user)
    
    def _calculate_health_score(self) -> float:
        """
        Calculate composite system health score (0.0 to 1.0).
        
        This combines multiple metrics into one easy-to-understand score.
        """
        health = 1.0  
       
        health -= min(self.error_rate * 5, 0.5)  
        
       
        if self.latency > 150:
            health -= min((self.latency - 150) / 500, 0.3)  
        
      
        if self.adoption_rate < 0.3:
            health -= 0.1
        
       
        return float(max(health, 0.0))
    
    def reset(self):
        """
        Reset all metrics to initial state.
        Called at the start of each new episode.
        """
        self.current_rollout = 0.0
        self.error_rate = self.config.get("base_error_rate", 0.01)
        self.latency = 100.0
        self.adoption_rate = 0.0
        self.revenue = 0.0
        self.consecutive_high_errors = 0
        self.last_error_rate = self.error_rate