"""
tests/test_server.py

Test the FastAPI server endpoints.
Run with: python tests/test_server.py
"""

import sys
import os
import time
import threading
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import httpx
import uvicorn
import pytest
from feature_flag_env.server.app import app


# Global server reference
server = None
server_thread = None


def start_test_server():
    """Start server in background thread for testing"""
    global server, server_thread
    
    def run_server():
        uvicorn.run(app, host="127.0.0.1", port=8001, log_level="error")
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for server to start
    for _ in range(20):
        try:
            with httpx.Client() as client:
                response = client.get("http://127.0.0.1:8001/health", timeout=1.0)
                if response.status_code == 200:
                    return
        except Exception:
            time.sleep(0.5)


@pytest.fixture(scope="module", autouse=True)
def server_fixture():
    """Ensure the test server is running for the whole module."""
    start_test_server()
    yield


def stop_test_server():
    """Stop the test server"""
    global server, server_thread
    # Server runs in daemon thread, will stop when main process exits


def test_health_endpoint():
    """Test /health endpoint"""
    print("🧪 Testing /health endpoint...")
    
    with httpx.Client() as client:
        response = client.get("http://127.0.0.1:8001/health")
        
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        
        data = response.json()
        assert data["status"] == "healthy", "Server should be healthy"
        assert data["environment_ready"] == True, "Environment should be ready"
        
        print(f"   ✅ Health check passed: {data['status']}")
    
    return True


def test_reset_endpoint():
    """Test /reset endpoint"""
    print("\n🧪 Testing /reset endpoint...")
    
    with httpx.Client() as client:
        response = client.post("http://127.0.0.1:8001/reset")
        
        assert response.status_code == 200, f"Reset failed: {response.status_code}"
        
        data = response.json()
        assert "observation" in data, "Response should have observation"
        assert "info" in data, "Response should have info"
        
        obs = data["observation"]
        assert obs["current_rollout_percentage"] == 0.0, "Initial rollout should be 0%"
        assert "error_rate" in obs, "Observation should have error_rate"
        assert "feature_name" in obs, "Observation should have feature_name"
        
        print(f"   ✅ Reset successful")
        print(f"   📊 Feature: {obs['feature_name']}")
        print(f"   📊 Initial rollout: {obs['current_rollout_percentage']}%")
    
    return True


def test_step_endpoint():
    """Test /step endpoint"""
    print("\n🧪 Testing /step endpoint...")
    
    with httpx.Client() as client:
        # First reset
        client.post("http://127.0.0.1:8001/reset")
        
        # Take a step
        action = {
            "action_type": "INCREASE_ROLLOUT",
            "target_percentage": 10.0,
            "reason": "Starting rollout"
        }
        
        response = client.post(
            "http://127.0.0.1:8001/step",
            json=action
        )
        
        assert response.status_code == 200, f"Step failed: {response.status_code}"
        
        data = response.json()
        assert "observation" in data, "Response should have observation"
        assert "reward" in data, "Response should have reward"
        assert "done" in data, "Response should have done flag"
        
        obs = data["observation"]
        assert obs["current_rollout_percentage"] == 10.0, "Rollout should be 10%"
        
        print(f"   ✅ Step successful")
        print(f"   📊 Rollout: {obs['current_rollout_percentage']}%")
        print(f"   📊 Reward: {data['reward']:+.2f}")
        print(f"   📊 Done: {data['done']}")
    
    return True


def test_state_endpoint():
    """Test /state endpoint"""
    print("\n🧪 Testing /state endpoint...")
    
    with httpx.Client() as client:
        # Reset and take a few steps first
        client.post("http://127.0.0.1:8001/reset")
        
        for i in range(3):
            action = {
                "action_type": "INCREASE_ROLLOUT",
                "target_percentage": float((i + 1) * 10),
                "reason": f"Step {i+1}"
            }
            client.post("http://127.0.0.1:8001/step", json=action)
        
        # Get state
        response = client.get("http://127.0.0.1:8001/state")
        
        assert response.status_code == 200, f"State failed: {response.status_code}"
        
        data = response.json()
        assert "episode_id" in data, "State should have episode_id"
        assert "step_count" in data, "State should have step_count"
        assert data["step_count"] == 3, f"Step count should be 3, got {data['step_count']}"
        
        print(f"   ✅ State retrieved successfully")
        print(f"   📊 Episode ID: {data['episode_id'][:8]}...")
        print(f"   📊 Step count: {data['step_count']}")
        print(f"   📊 Total reward: {data['total_reward']:+.2f}")
    
    return True


def test_invalid_action():
    """Test that invalid actions are rejected"""
    print("\n🧪 Testing Invalid Action Handling...")
    
    with httpx.Client() as client:
        # Reset first
        client.post("http://127.0.0.1:8001/reset")
        
        # Try invalid action type - should get HTTP 422 from Pydantic validation
        action = {
            "action_type": "INVALID_ACTION",
            "target_percentage": 50.0,
            "reason": "This should fail"
        }
        
        response = client.post(
            "http://127.0.0.1:8001/step",
            json=action
        )
        
        # ✅ FIXED: Now expects 422 (Pydantic validation error) instead of 400
        assert response.status_code in [400, 422], f"Should reject invalid action type, got {response.status_code}"
        print(f"   ✅ Invalid action_type rejected: HTTP {response.status_code}")
        
        # Try invalid percentage - should get HTTP 422 from Pydantic Field validation
        action = {
            "action_type": "INCREASE_ROLLOUT",
            "target_percentage": 150.0,  # Invalid!
            "reason": "This should fail"
        }
        
        response = client.post(
            "http://127.0.0.1:8001/step",
            json=action
        )
        
        # ✅ FIXED: Now expects 422 (Pydantic validation error) instead of 400
        assert response.status_code in [400, 422], f"Should reject invalid percentage, got {response.status_code}"
        print(f"   ✅ Invalid percentage rejected: HTTP {response.status_code}")
        
        print(f"   ✅ Invalid actions correctly rejected")
    
    return True


def test_info_endpoint():
    """Test /info endpoint"""
    print("\n🧪 Testing /info endpoint...")
    
    with httpx.Client() as client:
        response = client.get("http://127.0.0.1:8001/info")
        
        assert response.status_code == 200, f"Info failed: {response.status_code}"
        
        data = response.json()
        assert "name" in data, "Info should have name"
        assert "action_space" in data, "Info should have action_space"
        assert "observation_space" in data, "Info should have observation_space"
        
        print(f"   ✅ Info retrieved successfully")
        print(f"   📊 Environment: {data['name']}")
        print(f"   📊 Actions: {len(data['action_space'])} available")
    
    return True


def main():
    """Run all server tests"""
    print("=" * 60)
    print("🚀 FEATURE FLAG ENVIRONMENT - SERVER TESTS")
    print("=" * 60)
    print()
    
    # Start server
    print("🔧 Starting test server...")
    start_test_server()
    print("✅ Server started on http://127.0.0.1:8001")
    print()
    
    results = []
    results.append(test_health_endpoint())
    results.append(test_reset_endpoint())
    results.append(test_step_endpoint())
    results.append(test_state_endpoint())
    results.append(test_invalid_action())
    results.append(test_info_endpoint())
    
    # Stop server
    stop_test_server()
    
    print()
    print("=" * 60)
    if all(results):
        print("✅ ALL SERVER TESTS PASSED!")
        print("🎉 FastAPI server is working correctly!")
    else:
        print("❌ SOME TESTS FAILED. Review and fix errors.")
    print("=" * 60)


if __name__ == "__main__":
    main()