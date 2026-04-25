"""
tests/test_historical_patterns.py

Tests for PatternMemory, CustomerProfile, and PatternAnalyzer.
"""

import pytest
from feature_flag_env.historical_patterns import (
    PatternMemory, 
    CustomerProfile, 
    PatternAnalyzer, 
    DeploymentPattern
)

def test_pattern_memory_persistence():
    memory = PatternMemory(capacity=5)
    for i in range(10):
        memory.record_deployment({"max_rollout": 10 * i}, "success")
    
    assert len(memory.history) == 5
    assert memory.history[-1]["metrics"]["max_rollout"] == 90

def test_pattern_analyzer_risk_scaling():
    profile = CustomerProfile(customer_id="test", risk_tolerance=0.5)
    profile.add_pattern(DeploymentPattern(
        pattern_id="p1", 
        description="test", 
        critical_rollout_threshold=50.0, 
        expected_error_spike=0.1,
        risk_weight=0.5
    ))
    
    analyzer = PatternAnalyzer(profile)
    
    # Below threshold
    risk_low = analyzer.compute_risk(10.0, 0.01)
    # At threshold
    risk_high = analyzer.compute_risk(50.0, 0.01)
    # Above threshold
    risk_vhigh = analyzer.compute_risk(55.0, 0.01)
    
    assert risk_low < risk_high
    assert risk_high > 0

def test_historical_failure_impact():
    profile = CustomerProfile(customer_id="test", risk_tolerance=1.0)
    memory = profile.memory
    # Record failures at 40%
    for _ in range(3):
        memory.record_deployment({"max_rollout": 40.0}, "failure")
        
    analyzer = PatternAnalyzer(profile)
    
    # Approach the failure zone
    risk_zone = analyzer.compute_risk(38.0, 0.01)
    assert risk_zone >= 0.3

if __name__ == "__main__":
    pytest.main([__file__])
