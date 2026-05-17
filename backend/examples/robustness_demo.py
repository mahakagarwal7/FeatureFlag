import sys
import os
import random

# Ensure the root is in path
sys.path.append(os.getcwd())

from feature_flag_env.server.feature_flag_environment import make_environment
from feature_flag_env.models import FeatureFlagAction
from feature_flag_env.historical_patterns import CustomerProfile, DeploymentPattern

def final_e2e_test():
    print("💎 Starting Final End-to-End Robustness Test 💎")
    
    # 1. Setup Historical Patterns
    profile = CustomerProfile(customer_id="global_bank_v2", risk_tolerance=0.1)
    profile.add_pattern(DeploymentPattern(
        pattern_id="payment_timeout_cluster",
        description="Timeouts cluster heavily around 65% rollout",
        critical_rollout_threshold=65.0,
        expected_error_spike=0.15,
        risk_weight=1.0
    ))

    # 2. Initialize the ultimate environment configuration
    env = make_environment(
        scenario_config=None, # use default hard mission scenario
        stakeholders_enabled=True,
        mission_config="enterprise_payment_gateway",
        tools_enabled=True,
        chaos_enabled=True,
        hitl_enabled=True
    )
    env.set_customer_profile(profile)
    
    obs = env.reset()
    print(f"✅ Environment initialized for mission: {obs.mission_name}")
    
    done = False
    step = 0
    while not done and step < 100:
        step += 1
        
        # Decide action based on state
        rollout = obs.current_rollout_percentage
        error = obs.error_rate
        
        # Access the extra_context to see the risk
        risk = env.extra_context.get("pattern_risk", 0.0)
        
        print(f"Step {step:02d}: Rollout={rollout:.1f}%, Error={error:.3f}, Risk={risk:.2f}, Phase={obs.current_phase}")
        
        # Simple heuristic agent
        if risk > 0.8 or error > 0.04:
            action_type = "DECREASE_ROLLOUT"
            target = max(0.0, rollout - 10.0)
        elif risk > 0.5:
            action_type = "MAINTAIN"
            target = rollout
        else:
            action_type = "INCREASE_ROLLOUT"
            target = min(100.0, rollout + 5.0)

        # Occasional tool calls
        if step % 5 == 0:
            action = FeatureFlagAction(
                action_type="TOOL_CALL",
                target_percentage=rollout,
                tool_call={
                    "tool_name": "github",
                    "action_name": "get_cicd_status",
                    "params": {"branch": "main"}
                }
            )
        else:
            action = FeatureFlagAction(
                action_type=action_type,
                target_percentage=target
            )
            
        try:
            res = env.step(action)
            obs = res.observation
            done = res.done
            
            # Print highlights
            if obs.last_tool_result:
                print(f"  🛠️  Tool: {obs.last_tool_result.get('tool')} - Success: {obs.last_tool_result.get('success')}")
            if obs.chaos_incident:
                print(f"  🔥 CHAOS! {obs.chaos_incident.get('type')} active!")
            if obs.approval_status != "NONE":
                print(f"  ⚖️  HITL: {obs.approval_status}")
                
        except Exception as e:
            print(f"❌ CRASH AT STEP {step}!")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    print("\n" + "="*50)
    if obs.phases_completed >= obs.total_phases:
        print("🏆 MISSION ACCOMPLISHED! ALL PHASES COMPLETED.")
    else:
        print(f"⏹️ Episode finished. Phases completed: {obs.phases_completed}/{obs.total_phases}")
    
    print("✅ FINAL PIPELINE ROBUSTNESS VERIFIED.")

if __name__ == "__main__":
    final_e2e_test()
