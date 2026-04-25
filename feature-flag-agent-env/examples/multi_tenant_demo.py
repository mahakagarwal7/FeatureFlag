"""
examples/multi_tenant_demo.py

Demonstrates Multi-Tenant Wrapper and Data/RBAC Isolation.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from feature_flag_env.server.feature_flag_environment import make_environment
from feature_flag_env.models import FeatureFlagAction
from feature_flag_env.multi_tenant import TenantManager, TenantContext, TenantAwareEnv

def main():
    print("--- Multi-Tenant Demo: Data Isolation and RBAC ---")

    # 1. Setup Global Tenant Manager
    manager = TenantManager()

    # Create Org A: Active engineering tenant
    org_a = TenantContext(
        tenant_id="org_a_finance",
        role="admin",
        api_keys={"datadog": "dd_finance_789"},
        config={"strict_mode": True}
    )
    manager.register_tenant(org_a)

    # Create Org B: External auditor/viewer tenant
    org_b = TenantContext(
        tenant_id="org_b_auditors",
        role="viewer",
        api_keys={},
        config={"audit_mode": True}
    )
    manager.register_tenant(org_b)

    # 2. Instantiate physical environment
    core_env = make_environment(scenario_config={"scenario_name": "stable"})

    # 3. Create Tenant Aware Wrappers
    env_admin = TenantAwareEnv(core_env, manager, "org_a_finance")
    env_viewer = TenantAwareEnv(core_env, manager, "org_b_auditors")

    # --- Start Scenario ---
    print("\n[Admin Route]")
    obs_admin = env_admin.reset()
    print(f"Role: {obs_admin.extra_context['tenant_role']}")
    print(f"Initial Pattern Risk: {obs_admin.extra_context['tenant_pattern_risk']}")
    
    # Admin modifies rollout
    print("Admin increasing rollout to 20%...")
    action_1 = FeatureFlagAction(action_type="INCREASE_ROLLOUT", target_percentage=20.0, reason="Testing")
    res_admin = env_admin.step(action_1)
    print(f"Success! Current rollout: {res_admin.observation.current_rollout_percentage}%")

    print("\n[Viewer Route]")
    try:
        # Viewers cannot reset or execute rollout modifications
        print("Viewer attempting to increase rollout...")
        env_viewer.step(action_1)
    except PermissionError as e:
        print(f"RBAC Blocked: {str(e)}")
        
    print("Viewer attempting to MAINTAIN rollout...")
    action_view = FeatureFlagAction(action_type="MAINTAIN", target_percentage=20.0, reason="Observing")
    res_viewer = env_viewer.step(action_view)
    print(f"Viewer observed rollout at: {res_viewer.observation.current_rollout_percentage}%")
    
    # 4. Show Data Isolation
    print("\n[Data Isolation Result]")
    print(f"Admin Config: {res_admin.observation.extra_context['tenant_config']}")
    print(f"Viewer Config: {res_viewer.observation.extra_context['tenant_config']}")
    
    # Note: They have different baselines running
    admin_baseline = manager.get_anomaly_detector('org_a_finance').metrics_history['error_rate']
    viewer_baseline = manager.get_anomaly_detector('org_b_auditors').metrics_history['error_rate']
    print(f"Admin accumulated baseline records: {len(admin_baseline)}")
    print(f"Viewer accumulated baseline records: {len(viewer_baseline)}")


if __name__ == "__main__":
    main()
