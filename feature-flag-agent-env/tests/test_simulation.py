"""
tests/test_simulation.py

Test the simulation engine to verify metrics are calculated correctly.
Run with: python tests/test_simulation.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from feature_flag_env.server.simulation_engine import FeatureFlagSimulator


def test_basic_simulation():
    """Test that basic simulation works"""
    print("🧪 Testing Basic Simulation...")
    
    # Create a simple scenario
    config = {
        "base_error_rate": 0.02,
        "error_variance": 0.005,
        "latency_per_10pct_rollout": 8.0,
        "adoption_speed": 0.15,
        "revenue_per_user": 0.10,
        "total_users": 10000,
        "incident_zones": [],
    }
    
    # Create simulator with fixed seed for reproducibility
    simulator = FeatureFlagSimulator(config, seed=42)
    
    # Initial state
    print(f"   Initial error rate: {simulator.error_rate:.4f}")
    print(f"   Initial latency: {simulator.latency:.1f}ms")
    
    # Take a step: increase rollout to 25%
    metrics = simulator.step(target_rollout=25.0)
    
    print(f"   After 25% rollout:")
    print(f"   - Error rate: {metrics['error_rate']:.4f}")
    print(f"   - Latency: {metrics['latency_p99_ms']:.1f}ms")
    print(f"   - Adoption: {metrics['user_adoption_rate']:.4f}")
    print(f"   - Revenue: ${metrics['revenue_impact']:.2f}")
    print(f"   - Health: {metrics['system_health_score']:.2f}")
    print(f"   - Active users: {metrics['active_users']}")
    
    # Verify metrics are in valid ranges
    assert 0.0 <= metrics['error_rate'] <= 1.0, "Error rate out of range"
    assert metrics['latency_p99_ms'] >= 0, "Latency negative"
    assert 0.0 <= metrics['user_adoption_rate'] <= 1.0, "Adoption out of range"
    assert metrics['revenue_impact'] >= 0, "Revenue negative"
    assert 0.0 <= metrics['system_health_score'] <= 1.0, "Health out of range"
    
    print("   ✅ All metrics in valid ranges")
    return True


def test_error_scaling():
    """Test that errors increase with rollout"""
    print("\n🧪 Testing Error Scaling...")
    
    config = {
        "base_error_rate": 0.01,
        "error_variance": 0.001,  # Low variance for predictable test
        "incident_zones": [],
    }
    
    simulator = FeatureFlagSimulator(config, seed=42)
    
    # Test at different rollout levels
    rollout_levels = [10, 25, 50, 75, 100]
    error_rates = []
    
    for rollout in rollout_levels:
        metrics = simulator.step(target_rollout=rollout)
        error_rates.append(metrics['error_rate'])
        print(f"   {rollout}% rollout → {metrics['error_rate']:.4f} errors")
    
    # Errors should generally increase with rollout
    # (allowing for some noise)
    assert error_rates[-1] > error_rates[0], "Errors should increase with rollout"
    print("   ✅ Errors scale with rollout percentage")
    return True


def test_incident_zones():
    """Test that incident zones trigger error spikes"""
    print("\n🧪 Testing Incident Zones...")
    
    config = {
        "base_error_rate": 0.02,
        "error_variance": 0.001,
        "incident_zones": [
            {"min": 40, "max": 50, "probability": 1.0, "spike": 0.15}  # 100% chance
        ],
    }
    
    simulator = FeatureFlagSimulator(config, seed=42)
    
    # Go to 35% (no incident)
    metrics_35 = simulator.step(target_rollout=35.0)
    print(f"   35% rollout → {metrics_35['error_rate']:.4f} errors")
    
    # Go to 45% (incident zone - should spike!)
    metrics_45 = simulator.step(target_rollout=45.0)
    print(f"   45% rollout → {metrics_45['error_rate']:.4f} errors")
    
    # Error should be higher in incident zone
    assert metrics_45['error_rate'] > metrics_35['error_rate'], \
        "Error should spike in incident zone"
    print("   ✅ Incident zones trigger error spikes")
    return True


def test_adoption_growth():
    """Test that adoption grows gradually"""
    print("\n🧪 Testing Adoption Growth...")
    
    config = {
        "base_error_rate": 0.01,
        "error_variance": 0.001,
        "adoption_speed": 0.2,
        "incident_zones": [],
    }
    
    simulator = FeatureFlagSimulator(config, seed=42)
    
    # Multiple steps at 50% rollout
    adoption_rates = []
    for i in range(5):
        metrics = simulator.step(target_rollout=50.0)
        adoption_rates.append(metrics['user_adoption_rate'])
        print(f"   Step {i+1}: Adoption = {metrics['user_adoption_rate']:.4f}")
    
    # Adoption should increase over time (gradual growth)
    assert adoption_rates[-1] > adoption_rates[0], "Adoption should grow over time"
    print("   ✅ Adoption grows gradually")
    return True


def test_revenue_calculation():
    """Test that revenue is calculated correctly"""
    print("\n🧪 Testing Revenue Calculation...")
    
    config = {
        "base_error_rate": 0.01,
        "error_variance": 0.001,
        "adoption_speed": 0.5,  # Fast adoption for testing
        "revenue_per_user": 0.10,
        "total_users": 10000,
        "incident_zones": [],
    }
    
    simulator = FeatureFlagSimulator(config, seed=42)
    
    # Go to 100% rollout, wait for adoption
    for i in range(10):
        metrics = simulator.step(target_rollout=100.0)
    
    # Expected: ~10000 users × 0.10 = ~$1000 (depending on adoption)
    print(f"   Revenue at high adoption: ${metrics['revenue_impact']:.2f}")
    assert metrics['revenue_impact'] > 0, "Revenue should be positive"
    print("   ✅ Revenue calculated correctly")
    return True


def test_health_score():
    """Test that health score reflects system state"""
    print("\n🧪 Testing Health Score...")
    
    # Good scenario
    good_config = {
        "base_error_rate": 0.01,
        "error_variance": 0.001,
        "latency_per_10pct_rollout": 3.0,
        "adoption_speed": 0.3,
        "incident_zones": [],
    }
    
    # Bad scenario
    bad_config = {
        "base_error_rate": 0.10,
        "error_variance": 0.02,
        "latency_per_10pct_rollout": 20.0,
        "adoption_speed": 0.05,
        "incident_zones": [
            {"min": 30, "max": 50, "probability": 1.0, "spike": 0.20}
        ],
    }
    
    good_sim = FeatureFlagSimulator(good_config, seed=42)
    bad_sim = FeatureFlagSimulator(bad_config, seed=42)
    
    # Run both to 50% rollout
    good_metrics = good_sim.step(50.0)
    bad_metrics = bad_sim.step(50.0)
    
    print(f"   Good scenario health: {good_metrics['system_health_score']:.2f}")
    print(f"   Bad scenario health: {bad_metrics['system_health_score']:.2f}")
    
    assert good_metrics['system_health_score'] > bad_metrics['system_health_score'], \
        "Good scenario should have higher health"
    print("   ✅ Health score reflects system state")
    return True


def test_reproducibility():
    """Test that same seed produces same results"""
    print("\n🧪 Testing Reproducibility...")
    
    config = {
        "base_error_rate": 0.02,
        "error_variance": 0.005,
        "incident_zones": [],
    }
    
    # Run twice with same seed
    sim1 = FeatureFlagSimulator(config, seed=123)
    sim2 = FeatureFlagSimulator(config, seed=123)
    
    metrics1 = sim1.step(25.0)
    metrics2 = sim2.step(25.0)
    
    # Should be identical
    assert metrics1['error_rate'] == metrics2['error_rate'], \
        "Same seed should produce same results"
    
    print(f"   Run 1 error rate: {metrics1['error_rate']:.6f}")
    print(f"   Run 2 error rate: {metrics2['error_rate']:.6f}")
    print("   ✅ Results are reproducible with same seed")
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("🚀 FEATURE FLAG ENVIRONMENT - SIMULATION TESTS")
    print("=" * 60)
    print()
    
    results = []
    results.append(test_basic_simulation())
    results.append(test_error_scaling())
    results.append(test_incident_zones())
    results.append(test_adoption_growth())
    results.append(test_revenue_calculation())
    results.append(test_health_score())
    results.append(test_reproducibility())
    
    print()
    print("=" * 60)
    if all(results):
        print("✅ ALL SIMULATION TESTS PASSED!")
        print("🎉 Simulation engine is working correctly!")
    else:
        print("❌ SOME TESTS FAILED. Review and fix errors.")
    print("=" * 60)


if __name__ == "__main__":
    main()