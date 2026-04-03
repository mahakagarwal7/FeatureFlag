#!/usr/bin/env python
"""
Verification script for API Authentication & Security feature
Run: python verify_security.py
"""
import sys
import subprocess

print("=" * 70)
print("API SECURITY FEATURE - VERIFICATION RUNBOOK")
print("=" * 70)

tests = [
    ("1️⃣  Verify imports work", [
        "python", "-c",
        "from feature_flag_env.server.app import app; from feature_flag_env.server.security import config; print('✅ Server and security modules import OK')"
    ]),
    
    ("2️⃣  Check security is disabled by default", [
        "python", "-c",
        "from feature_flag_env.server.security import config; print(f'✅ Security enabled: {config.enabled}\\n   Require auth: {config.require_auth}\\n   Audit logging: {config.enable_audit_logging}\\n   Rate limiting: {config.enable_rate_limiting}')"
    ]),
    
    ("3️⃣  Run security module tests", [
        "python", "-m", "pytest", "tests/test_security.py", "-q", "--ignore=test_results.txt"
    ]),
    
    ("4️⃣  Run ensemble + HITL tests", [
        "python", "-m", "pytest", "tests/test_ensemble_agent.py", "tests/test_human_in_loop_agent.py", "-q", "--ignore=test_results.txt"
    ]),
    
    ("5️⃣  Verify no code errors", [
        "python", "-m", "py_compile",
        "feature_flag_env/server/security.py",
        "feature_flag_env/server/app.py"
    ]),
    
    ("6️⃣  Check existing pipeline works (baseline agent)", [
        "python", "inference.py", "--agent", "baseline", "--episodes", "1", "--task", "task1"
    ]),
    
    ("7️⃣  Check HITL agent works", [
        "python", "inference.py", "--agent", "human_in_loop", "--episodes", "1", "--task", "task1", "--hitl-threshold", "0.9", "--hitl-no-prompt"
    ]),
    
    ("8️⃣  Check ensemble agent works", [
        "python", "inference.py", "--agent", "ensemble", "--episodes", "1", "--task", "task1", "--ensemble-strategy", "majority"
    ]),
]

passed = 0
failed = 0

for test_name, cmd in tests:
    print(f"\n{test_name}")
    print("-" * 70)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print(result.stdout)
            passed += 1
        else:
            print(f"❌ FAILED")
            if result.stderr:
                print(f"Error: {result.stderr[:500]}")
            failed += 1
    except subprocess.TimeoutExpired:
        print(f"❌ TIMEOUT (exceeded 120 seconds)")
        failed += 1
    except Exception as e:
        print(f"❌ ERROR: {e}")
        failed += 1

print("\n" + "=" * 70)
print(f"RESULTS: {passed} passed ✅, {failed} failed ❌")
print("=" * 70)

if failed == 0:
    print("\n🎉 ALL CHECKS PASSED! Security feature is working correctly.")
    sys.exit(0)
else:
    print(f"\n⚠️  {failed} check(s) failed. See above for details.")
    sys.exit(1)
