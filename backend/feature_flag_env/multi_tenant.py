"""
feature_flag_env/multi_tenant.py

Multi-Tenant Wrapper Architecture for the Enterprise Deployment Simulator.
Sits OUTSIDE the core environment, providing Context, RBAC, and Data Isolation.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging

from feature_flag_env.models import FeatureFlagObservation, StepResponse, FeatureFlagAction
from feature_flag_env.anomaly_detection import AnomalyDetector
from feature_flag_env.historical_patterns import CustomerProfile, PatternAnalyzer


@dataclass
class TenantContext:
    tenant_id: str
    role: str  # e.g., "admin", "engineer", "viewer"
    api_keys: Dict[str, str] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)


class TenantManager:
    """Manages organizations and persistent, isolated data per tenant."""
    def __init__(self):
        self._tenants: Dict[str, TenantContext] = {}
        
        # Isolated data layers outlasting single episodes
        self._anomaly_detectors: Dict[str, AnomalyDetector] = {}
        self._customer_profiles: Dict[str, CustomerProfile] = {}
        self._pattern_analyzers: Dict[str, PatternAnalyzer] = {}

    def register_tenant(self, context: TenantContext):
        self._tenants[context.tenant_id] = context
        
        # Initialize isolated telemetry and diagnostic data
        if context.tenant_id not in self._anomaly_detectors:
            self._anomaly_detectors[context.tenant_id] = AnomalyDetector()
            profile = CustomerProfile(customer_id=context.tenant_id)
            self._customer_profiles[context.tenant_id] = profile
            self._pattern_analyzers[context.tenant_id] = PatternAnalyzer(profile)

    def get_context(self, tenant_id: str) -> Optional[TenantContext]:
        return self._tenants.get(tenant_id)

    def get_anomaly_detector(self, tenant_id: str) -> AnomalyDetector:
        return self._anomaly_detectors[tenant_id]

    def get_pattern_analyzer(self, tenant_id: str) -> PatternAnalyzer:
        return self._pattern_analyzers[tenant_id]


class TenantAwareEnv:
    """
    Wrapper around the core FeatureFlagEnvironment.
    Injects context, enforces RBAC, and isolates telemetry per tenant.
    """
    def __init__(self, env, tenant_manager: TenantManager, active_tenant_id: str):
        """
        Args:
            env: The instantiated, core FeatureFlagEnvironment.
            tenant_manager: The global TenantManager holding configurations.
            active_tenant_id: The ID of the tenant utilizing this wrapped instance.
        """
        self.env = env
        self.tenant_manager = tenant_manager
        self.active_tenant_id = active_tenant_id
        
        self.ctx = self.tenant_manager.get_context(self.active_tenant_id)
        if not self.ctx:
            raise ValueError(f"Tenant '{self.active_tenant_id}' is not registered.")
            
        logging.info(f"Initialized env wrapper for tenant: {self.active_tenant_id} (Role: {self.ctx.role})")

    # --- Property Passthrough ---
    @property
    def observation_space(self):
        return self.env.observation_space

    @property
    def analytics(self):
        return self.env.analytics

    # --- RBAC ---
    def _check_rbac(self, allowed_roles: List[str], action_name: str):
        if self.ctx.role not in allowed_roles:
            raise PermissionError(
                f"RBAC Violation: Tenant '{self.active_tenant_id}' with role '{self.ctx.role}' "
                f"is not permitted to execute '{action_name}'."
            )

    # --- Environmental Methods ---
    def reset(self, *args, **kwargs) -> FeatureFlagObservation:
        """Enforces RBAC and injects tenant-specific context into the observation."""
        self._check_rbac(["admin", "engineer"], "reset")
        
        obs = self.env.reset(*args, **kwargs)
        obs = self._apply_tenant_context(obs)
        return obs

    def step(self, action: FeatureFlagAction) -> StepResponse:
        """Enforces action-level RBAC, runs core env, and updates isolated tenant data."""
        
        role = self.ctx.role
        atype = action.action_type
        
        # RBAC Definitions (Simple Version)
        if atype in ["FULL_ROLLOUT", "ROLLBACK"]:
            self._check_rbac(["admin"], "Execute Critical Stage")
        elif atype in ["INCREASE_ROLLOUT", "DECREASE_ROLLOUT"]:
            self._check_rbac(["admin", "engineer"], "Modify Rollout")
        elif atype == "TOOL_CALL":
            self._check_rbac(["admin", "engineer"], "Execute External Tool")
        elif atype == "MAINTAIN":
            # Viewers can only "Maintain" (observe the environment)
            self._check_rbac(["admin", "engineer", "viewer"], "Maintain State")
            
        # Execute core logic
        res = self.env.step(action)
        
        # Isolate telemetry updates
        self._update_tenant_baselines(res.observation)
        
        # Inject contextual state
        res.observation = self._apply_tenant_context(res.observation)
        return res

    def _update_tenant_baselines(self, obs: FeatureFlagObservation):
        """Update the long-living anomaly baselines strictly for this tenant."""
        detector = self.tenant_manager.get_anomaly_detector(self.active_tenant_id)
        metrics = {
            "error_rate": obs.error_rate,
            "latency_p99_ms": obs.latency_p99_ms,
            "revenue_impact": obs.revenue_impact,
            "system_health_score": obs.system_health_score
        }
        detector.update_baselines(metrics)

    def _apply_tenant_context(self, obs: FeatureFlagObservation) -> FeatureFlagObservation:
        """Hydrate extra_context with tenant data overrides instead of global ones."""
        # Calculate Anomaly
        detector = self.tenant_manager.get_anomaly_detector(self.active_tenant_id)
        metrics = {
            "error_rate": obs.error_rate,
            "latency_p99_ms": obs.latency_p99_ms,
            "revenue_impact": obs.revenue_impact,
            "system_health_score": obs.system_health_score
        }
        obs.extra_context["tenant_anomaly"] = detector.detect(metrics)
        
        # Calculate Pattern Risk
        analyzer = self.tenant_manager.get_pattern_analyzer(self.active_tenant_id)
        obs.extra_context["tenant_pattern_risk"] = analyzer.compute_risk(
            obs.current_rollout_percentage, obs.error_rate
        )
        
        # Add metadata
        obs.extra_context["tenant_id"] = self.ctx.tenant_id
        obs.extra_context["tenant_role"] = self.ctx.role
        obs.extra_context["tenant_config"] = self.ctx.config
        
        return obs
