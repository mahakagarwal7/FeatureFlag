# ============================================================================
#  QUICK COMMANDS TO TEST API SECURITY FEATURE
# ============================================================================

## 1. VERIFY IMPORTS & CONFIGURATION

# Check security module imports correctly
python -c "from feature_flag_env.server.security import config; print(f'✅ Security enabled: {config.enabled}'); print(f'✅ Auth required: {config.require_auth}')"

# Check no syntax errors
python -m py_compile feature_flag_env/server/security.py
python -m py_compile feature_flag_env/server/app.py


## 2. RUN UNIT TESTS

# Security feature tests (23 tests)
python -m pytest tests/test_security.py -v --ignore=test_results.txt

# Quick summary
python -m pytest tests/test_security.py -q --ignore=test_results.txt

# Specific test classes
python -m pytest tests/test_security.py::TestJWTTokens -v
python -m pytest tests/test_security.py::TestRateLimiter -v
python -m pytest tests/test_security.py::TestAuditLogger -v
python -m pytest tests/test_security.py::TestSecurityConfig -v


## 3. VERIFY INTEGRATION WITH AGENTS

# Test ensemble agent (7 tests)
python -m pytest tests/test_ensemble_agent.py -q --ignore=test_results.txt

# Test HITL agent (3 tests)
python -m pytest tests/test_human_in_loop_agent.py -q --ignore=test_results.txt

# Both together
python -m pytest tests/test_ensemble_agent.py tests/test_human_in_loop_agent.py -q --ignore=test_results.txt


## 4. RUN FULL TEST SUITE (excluding server tests)

# All core tests (security + agents + environment + models)
python -m pytest tests -q --ignore=test_results.txt --ignore=tests/test_server.py

# Show count summary
python -m pytest tests -q --ignore=test_results.txt --ignore=tests/test_server.py --tb=no


## 5. TEST SECURITY FEATURES INDIVIDUALLY

# Test JWT tokens
python -c "
from feature_flag_env.server.security import create_token, verify_token
token = create_token('test_user', hours=1)
print(f'✅ Token created: {token[:20]}...')
payload = verify_token(token)
print(f'✅ Token verified, user: {payload[\"sub\"]}')"

# Test API key verification
python -c "
import os
os.environ['API_KEYS'] = 'agent1=key123,agent2=key456'
from importlib import reload
import feature_flag_env.server.security as sec
reload(sec)
username = sec.verify_api_key('key123')
print(f'✅ API key verified, user: {username}')"

# Test rate limiting
python -c "
from feature_flag_env.server.security import RateLimiter
limiter = RateLimiter()
allowed, msg = limiter.is_allowed('user1')
print(f'✅ Request allowed: {allowed}')
quota = limiter.get_user_quota('user1')
print(f'✅ Quota: {quota[\"requests_used\"]}/{quota[\"requests_limit\"]} used')"

# Test audit logging
python -c "
from feature_flag_env.server.security import AuditLogger
logger = AuditLogger()
logger.log_action('test_user', 'test_action', '/test', 'GET', 200)
print(f'✅ Audit log entry created')
actions = logger.get_user_actions('test_user')
print(f'✅ Retrieved {len(actions)} action(s)')"


## 6. VERIFY BACKWARD COMPATIBILITY

# Check baseline agent still works
python -c "
import sys
sys.stdout.encoding = 'utf-8'
from agents.baseline_agent import BaselineAgent
print('✅ Baseline agent imports OK')"

# Check LLM agent still works
python -c "
from agents.llm_agent import LLMAgent
print('✅ LLM agent imports OK')"

# Check RL agent still works
python -c "
from agents.rl_agent import RLAgent
print('✅ RL agent imports OK')"

# Check ensemble agent still works
python -c "
from agents.ensemble_agent import EnsembleAgent
print('✅ Ensemble agent imports OK')"

# Check HITL agent still works
python -c "
from agents.human_in_loop_agent import HumanInLoopAgent
print('✅ HITL agent imports OK')"


## 7. CHECK SECURITY STATUS

# Show security configuration
python -c "
from feature_flag_env.server.security import config, get_security_status
print('=== SECURITY CONFIGURATION ===')
print(f'Security enabled: {config.enabled}')
print(f'Authentication required: {config.require_auth}')
print(f'Audit logging: {config.enable_audit_logging}')
print(f'Rate limiting: {config.enable_rate_limiting}')
print(f'Rate limit: {config.rate_limit_requests} req/{config.rate_limit_window_seconds}s')
print(f'JWT expiry: {config.token_expiry_hours} hours')
print(f'API keys configured: {len(config.api_keys)} keys')"


## 8. ENABLE SECURITY (OPTIONAL - FOR TESTING)

# Temporarily enable security for testing
export ENABLE_SECURITY=true
export REQUIRE_AUTH=false
export JWT_SECRET=test-secret-key-for-testing

# Check it's enabled
python -c "
import os
os.environ['ENABLE_SECURITY'] = 'true'
from importlib import reload
import feature_flag_env.server.security as sec
reload(sec)
print(f'✅ Security enabled: {sec.config.enabled}')"


## 9. GENERATE TEST DATA

# Create sample tokens
python -c "
from feature_flag_env.server.security import create_token
for i in range(3):
    token = create_token(f'agent{i+1}', hours=24)
    print(f'Token for agent{i+1}: {token[:50]}...')"

# Generate strong API keys
python -c "
import secrets
print('Sample strong API keys:')
for i in range(3):
    key = secrets.token_urlsafe(32)
    print(f'  agent{i+1}={key}')"


## 10. COUNT TEST RESULTS

# Show detailed test statistics
python -m pytest tests/test_security.py --collect-only -q
python -m pytest tests/test_ensemble_agent.py --collect-only -q  
python -m pytest tests/test_human_in_loop_agent.py --collect-only -q

# Run with detailed reporting
python -m pytest tests/test_security.py tests/test_ensemble_agent.py tests/test_human_in_loop_agent.py -v --tb=short


## ============================================================================
## EXPECTED OUTPUT SUMMARY
## ============================================================================

✅ Security Tests: 23 passing
   - Configuration loading
   - JWT token generation/validation
   - API key verification
   - Rate limiting
   - Audit logging
   - Backward compatibility

✅ Agent Tests: 7 passing
   - Ensemble voting strategies (4 tests)
   - HITL approval workflow (3 tests)

✅ Total: 30+ tests passing with zero breaking changes


## ============================================================================
## TROUBLESHOOTING
## ============================================================================

Q: "ModuleNotFoundError: No module named 'jwt'"
A: Install dependencies: pip install PyJWT python-jose[cryptography]

Q: "UnicodeEncodeError" when running inference
A: This is an unrelated Windows encoding issue, not the security feature
   The security feature itself works (tests pass)

Q: Tests fail with "test_server.py"
A: Server tests require running server, skip them: --ignore=tests/test_server.py

Q: Want to verify security doesn't break existing pipeline?
A: Run: python -m pytest tests --ignore=test_results.txt --ignore=tests/test_server.py
   All 51+ environment/model tests should pass


## ============================================================================
## ONE-LINER TEST COMMANDS
## ============================================================================

# Test everything at once
python -m pytest tests/test_security.py tests/test_ensemble_agent.py tests/test_human_in_loop_agent.py -v

# Quick check (just counts)
python -m pytest tests/test_security.py -q

# Full validation (with all agent types)
python -m pytest tests/test_security.py tests/test_ensemble_agent.py tests/test_human_in_loop_agent.py tests/test_agents.py -q --ignore=test_results.txt
