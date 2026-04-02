"""
feature_flag_env/tasks/graders.py

Graders for all 3 tasks.
Each grader scores trajectories from 0.0 to 1.0
"""

from typing import List, Dict, Any
from feature_flag_env.models import FeatureFlagObservation, FeatureFlagAction


class BaseGrader:
    """Base grader class with common utilities"""
    
    def _normalize(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize value to 0.0-1.0 range"""
        if max_val == min_val:
            return 1.0
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


class Task1Grader(BaseGrader):
    """
    Task 1: Safe Small Rollout (EASY)
    
    Goal: Reach 25% rollout safely without exceeding error thresholds
    
    Scoring:
    - 40%: Reach 25% rollout
    - 30%: Keep error rate < 5%
    - 20%: Complete within 10 steps
    - 10%: No rollbacks
    """
    
    def grade(self, trajectory: List[Dict[str, Any]]) -> float:
        """
        Grade Task 1 trajectory.
        
        Args:
            trajectory: List of step dictionaries with observation, action, reward
            
        Returns:
            float: Score from 0.0 to 1.0
        """
        if not trajectory:
            return 0.0
        
        final_obs = trajectory[-1]["observation"]
        num_steps = len(trajectory)
        
        # ========== 1. ROLLOUT ACHIEVEMENT (40%) ==========
        # Band-based scoring: prefer 23-27, penalize 30 compared to target band.
        target_rollout = 25.0
        rollout = final_obs.current_rollout_percentage

        if 23.0 <= rollout <= 27.0:
            rollout_score = 1.0
        elif 20.0 <= rollout < 23.0 or 27.0 < rollout <= 30.0:
            rollout_score = 0.7
        else:
            rollout_score = self._normalize(rollout, 0.0, target_rollout * 1.5)
        
        # ========== 2. ERROR RATE COMPLIANCE (30%) ==========
        max_error_threshold = 0.05  # 5%
        max_error_in_episode = max(
            step["observation"].error_rate for step in trajectory
        )
        error_score = 1.0 if max_error_in_episode <= max_error_threshold else 0.0
        
        # ========== 3. STEP EFFICIENCY (20%) ==========
        max_steps = 10
        step_score = max(0.0, 1.0 - ((num_steps - 1) / max_steps))
        
        # ========== 4. NO ROLLBACKS (10%) ==========
        has_rollback = any(
            step["action"].action_type == "ROLLBACK"
            for step in trajectory
        )
        rollback_score = 0.0 if has_rollback else 1.0
        
        # ========== FINAL SCORE ==========
        final_score = (
            0.40 * rollout_score +
            0.30 * error_score +
            0.20 * step_score +
            0.10 * rollback_score
        )
        
        return round(final_score, 3)


class Task2Grader(BaseGrader):
    """
    Task 2: Risk-Aware Scaling (MEDIUM)
    
    Goal: Scale to ~70% while responding to incidents
    
    Scoring:
    - 35%: Reach ~70% final rollout (best in the 65-70 band)
    - 30%: Respond to incidents correctly
    - 20%: Recover after incidents
    - 15%: Maintain latency < 200ms
    """
    
    def grade(self, trajectory: List[Dict[str, Any]]) -> float:
        """
        Grade Task 2 trajectory.
        
        Args:
            trajectory: List of step dictionaries
            
        Returns:
            float: Score from 0.0 to 1.0
        """
        if not trajectory:
            return 0.0
        
        final_obs = trajectory[-1]["observation"]
        
        # ========== 1. FINAL ROLLOUT (35%) ==========
        target_rollout = 70.0
        rollout = final_obs.current_rollout_percentage
        if 65.0 <= rollout <= 70.0:
            rollout_score = 1.0
        elif rollout > 70.0:
            rollout_score = max(0.0, 1.0 - ((rollout - 70.0) / 30.0))
        else:
            rollout_score = self._normalize(rollout, 0.0, target_rollout)
        
        # ========== 2. INCIDENT RESPONSE (30%) ==========
        # Check if agent decreased rollout when errors spiked
        incident_responded = False
        for i, step in enumerate(trajectory):
            obs = step["observation"]
            if obs.error_rate > 0.10:  # Error spike detected
                # Check if next action decreased rollout
                if i + 1 < len(trajectory):
                    next_obs = trajectory[i + 1]["observation"]
                    if next_obs.current_rollout_percentage < obs.current_rollout_percentage:
                        incident_responded = True
                        break
        
        incident_score = 1.0 if incident_responded else 0.0
        
        # ========== 3. RECOVERY (20%) ==========
        # Check if errors recovered after incident
        recovered = final_obs.error_rate < 0.05
        recovery_score = 1.0 if recovered else 0.0
        
        # ========== 4. LATENCY COMPLIANCE (15%) ==========
        max_latency_threshold = 200.0  # ms
        max_latency = max(
            step["observation"].latency_p99_ms for step in trajectory
        )
        latency_score = 1.0 if max_latency <= max_latency_threshold else 0.5
        
        # ========== FINAL SCORE ==========
        final_score = (
            0.35 * rollout_score +
            0.30 * incident_score +
            0.20 * recovery_score +
            0.15 * latency_score
        )
        
        return round(final_score, 3)


class Task3Grader(BaseGrader):
    """
    Task 3: Multi-Objective Optimization (HARD)
    
    Goal: Maximize revenue while balancing adoption, risk, and health
    
    Scoring:
    - 25%: Cumulative revenue
    - 20%: Final adoption rate
    - 20%: Average system health
    - 15%: Final rollout attainment (toward 100%)
    - 10%: Balance score
    - 10%: No catastrophic failures
    """
    
    def grade(self, trajectory: List[Dict[str, Any]]) -> float:
        """
        Grade Task 3 trajectory.
        
        Args:
            trajectory: List of step dictionaries
            
        Returns:
            float: Score from 0.0 to 1.0
        """
        if not trajectory:
            return 0.0
        
        final_obs = trajectory[-1]["observation"]
        
        # ========== 1. CUMULATIVE REVENUE (25%) ==========
        total_revenue = sum(step["observation"].revenue_impact for step in trajectory)
        # Normalize: assume $5000 is excellent for 50 steps
        revenue_score = self._normalize(total_revenue, 0.0, 5000.0)
        
        # ========== 2. FINAL ADOPTION RATE (20%) ==========
        target_adoption = 0.80  # 80%
        adoption_score = self._normalize(
            final_obs.user_adoption_rate,
            0.0,
            target_adoption
        )
        
        # ========== 3. AVERAGE SYSTEM HEALTH (20%) ==========
        avg_health = sum(
            step["observation"].system_health_score for step in trajectory
        ) / len(trajectory)
        health_score = avg_health  # Already 0.0-1.0

        # ========== 4. FINAL ROLLOUT ATTAINMENT (15%) ==========
        rollout_score = self._normalize(final_obs.current_rollout_percentage, 0.0, 100.0)
        
        # ========== 5. BALANCE SCORE (10%) ==========
        # How well did agent balance competing objectives?
        balance_score = min(
            (adoption_score + health_score + rollout_score + (1.0 - final_obs.error_rate)) / 4.0,
            1.0
        )
        
        # ========== 6. NO CATASTROPHIC FAILURES (10%) ==========
        max_error = max(step["observation"].error_rate for step in trajectory)
        catastrophe_penalty = 0.5 if max_error > 0.20 else 0.0
        failure_score = 1.0 - catastrophe_penalty
        
        # ========== FINAL SCORE ==========
        final_score = (
            0.25 * revenue_score +
            0.20 * adoption_score +
            0.20 * health_score +
            0.15 * rollout_score +
            0.10 * balance_score +
            0.10 * failure_score
        )
        
        return round(final_score, 3)


# =============================================================================
# HELPER: Get Grader by Task Name
# =============================================================================
def get_grader(task_name: str) -> BaseGrader:
    """
    Factory function to get grader by task name.
    
    Args:
        task_name: "task1", "task2", or "task3"
        
    Returns:
        BaseGrader: Appropriate grader instance
    """
    graders = {
        "task1": Task1Grader(),
        "task2": Task2Grader(),
        "task3": Task3Grader(),
    }
    return graders.get(task_name.lower(), Task1Grader())