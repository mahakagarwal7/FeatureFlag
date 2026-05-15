"""
tests/test_multi_tenant.py

Unit tests for the Multi-Tenant architecture.
Verifies RBAC enforcement and isolated data storage.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
from feature_flag_env.server.feature_flag_environment import make_environment
from feature_flag_env.models import FeatureFlagAction
from feature_flag_env.multi_tenant import TenantManager, TenantContext, TenantAwareEnv


class TestMultiTenantArchitecture(unittest.TestCase):
    def setUp(self):
        self.manager = TenantManager()
        self.org_admin = TenantContext(tenant_id="org_a", role="admin")
        self.org_eng = TenantContext(tenant_id="org_b", role="engineer")
        self.org_viewer = TenantContext(tenant_id="org_c", role="viewer")
        
        self.manager.register_tenant(self.org_admin)
        self.manager.register_tenant(self.org_eng)
        self.manager.register_tenant(self.org_viewer)
        
        self.core_env = make_environment(scenario_config={"scenario_name": "stable"})

    def test_rbac_viewer_blocked_from_reset(self):
        env_viewer = TenantAwareEnv(self.core_env, self.manager, "org_c")
        with self.assertRaises(PermissionError):
            env_viewer.reset()

    def test_rbac_admin_full_access(self):
        env_admin = TenantAwareEnv(self.core_env, self.manager, "org_a")
        # Admin can reset
        obs = env_admin.reset()
        self.assertEqual(obs.extra_context["tenant_id"], "org_a")
        
        # Admin can full rollout
        action = FeatureFlagAction(action_type="FULL_ROLLOUT", target_percentage=100.0, reason="test")
        res = env_admin.step(action)
        self.assertEqual(res.observation.current_rollout_percentage, 100.0)

    def test_rbac_engineer_restricted_access(self):
        # Engineer can reset
        env_eng = TenantAwareEnv(self.core_env, self.manager, "org_b")
        env_eng.reset()
        
        # Engineer can increase rollout
        action_inc = FeatureFlagAction(action_type="INCREASE_ROLLOUT", target_percentage=10.0, reason="test")
        env_eng.step(action_inc)
        
        # Engineer CANNOT full rollout
        action_full = FeatureFlagAction(action_type="FULL_ROLLOUT", target_percentage=100.0, reason="test")
        with self.assertRaises(PermissionError):
            env_eng.step(action_full)

    def test_data_isolation(self):
        env_admin = TenantAwareEnv(self.core_env, self.manager, "org_a")
        env_eng = TenantAwareEnv(self.core_env, self.manager, "org_b")
        
        env_admin.reset()
        action = FeatureFlagAction(action_type="INCREASE_ROLLOUT", target_percentage=20.0, reason="test")
        env_admin.step(action)
        env_admin.step(action)
        
        # Org A should have 2 history events (from the 2 steps)
        admin_detector = self.manager.get_anomaly_detector("org_a")
        self.assertEqual(len(admin_detector.metrics_history["error_rate"]), 2)
        
        # Org B should have 0
        eng_detector = self.manager.get_anomaly_detector("org_b")
        self.assertEqual(len(eng_detector.metrics_history["error_rate"]), 0)


if __name__ == "__main__":
    unittest.main()
