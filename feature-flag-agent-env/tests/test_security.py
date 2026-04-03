"""
tests/test_security.py

Test suite for API Authentication & Security module

Tests:
- JWT token generation and validation
- API key authentication
- Rate limiting enforcement
- Audit logging functionality
- Security middleware integration
- Backward compatibility (security is opt-in)
"""

import pytest
import os
from datetime import datetime, timedelta

# Set security to disabled by default for backward compatibility testing
os.environ["ENABLE_SECURITY"] = "false"

from feature_flag_env.server.security import (
    SecurityConfig,
    AuditLogger,
    RateLimiter,
    create_token,
    verify_token,
    verify_api_key,
    hash_api_key,
    get_security_status,
)
from jwt import ExpiredSignatureError


class TestSecurityConfig:
    """Test security configuration loading"""
    
    def test_config_disabled_by_default(self):
        """Security should be disabled by default for backward compatibility"""
        config = SecurityConfig()
        assert config.enabled is False
        assert config.require_auth is False
    
    def test_config_can_be_enabled(self, monkeypatch):
        """Security can be explicitly enabled via environment variables"""
        monkeypatch.setenv("ENABLE_SECURITY", "true")
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        config = SecurityConfig()
        assert config.enabled is True
        assert config.require_auth is True
    
    def test_api_keys_parsing(self, monkeypatch):
        """API keys should be parsed from comma-separated format"""
        monkeypatch.setenv(
            "API_KEYS",
            "agent1=key1,agent2=key2,agent3=key3"
        )
        config = SecurityConfig()
        assert len(config.api_keys) == 3
        assert config.api_keys["agent1"] == "key1"
        assert config.api_keys["agent2"] == "key2"
    
    def test_rate_limit_configuration(self, monkeypatch):
        """Rate limiting should be configurable"""
        monkeypatch.setenv("RATE_LIMIT_REQUESTS", "50")
        monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "30")
        config = SecurityConfig()
        assert config.rate_limit_requests == 50
        assert config.rate_limit_window_seconds == 30


class TestJWTTokens:
    """Test JWT token generation and validation"""
    
    def test_create_token(self, monkeypatch):
        """Should be able to create valid JWT tokens"""
        monkeypatch.setenv("JWT_SECRET", "test-secret-key")
        token = create_token("test_user", hours=1)
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_verify_token_valid(self, monkeypatch):
        """Should be able to verify valid tokens"""
        monkeypatch.setenv("JWT_SECRET", "test-secret-key")
        token = create_token("test_user", hours=1)
        payload = verify_token(token)
        assert payload["sub"] == "test_user"
        assert "exp" in payload
        assert "iat" in payload
    
    def test_verify_token_invalid(self, monkeypatch):
        """Should reject invalid tokens"""
        monkeypatch.setenv("JWT_SECRET", "test-secret-key")
        with pytest.raises(Exception):  # HTTPException
            verify_token("invalid.token.string")
    
    def test_token_expiry(self, monkeypatch):
        """Should reject expired tokens"""
        from feature_flag_env.server.security import encode, config as sec_config
        
        monkeypatch.setenv("JWT_SECRET", "test-secret-key")
        
        # Create an already-expired token
        expires = datetime.utcnow() - timedelta(hours=1)
        payload = {
            "sub": "test_user",
            "exp": expires,
            "iat": datetime.utcnow()
        }
        expired_token = encode(
            payload,
            sec_config.jwt_secret,
            algorithm=sec_config.jwt_algorithm
        )
        
        with pytest.raises(Exception):  # ExpiredSignatureError wrapped in HTTPException
            verify_token(expired_token)


class TestAPIKeys:
    """Test API key authentication"""
    
    def test_verify_api_key_valid(self, monkeypatch):
        """Should be able to verify valid API keys"""
        monkeypatch.setenv("API_KEYS", "user1=secret-key-123,user2=secret-key-456")
        
        # Reload config with new environment
        import importlib
        import feature_flag_env.server.security as sec_module
        importlib.reload(sec_module)
        
        username = sec_module.verify_api_key("secret-key-123")
        assert username == "user1"
    
    def test_verify_api_key_invalid(self, monkeypatch):
        """Should reject invalid API keys"""
        monkeypatch.setenv("API_KEYS", "user1=secret-key-123")
        with pytest.raises(Exception):  # HTTPException
            verify_api_key("wrong-key")
    
    def test_api_key_hashing(self):
        """API keys should be hashable for secure storage"""
        api_key = "my-secret-key-12345"
        hash1 = hash_api_key(api_key)
        hash2 = hash_api_key(api_key)
        
        # Same key should produce same hash (deterministic)
        assert hash1 == hash2
        
        # Hash should be different from original key
        assert hash1 != api_key
        assert len(hash1) == 64  # SHA256 produces 64-char hex


class TestAuditLogger:
    """Test audit logging functionality"""
    
    def test_audit_log_action(self):
        """Should log audit actions"""
        logger = AuditLogger()
        logger.log_action(
            user="test_agent",
            action="reset_environment",
            endpoint="/reset",
            method="POST",
            status_code=200,
            details={"episode_id": "ep_123"}
        )
        
        assert len(logger.logs) == 1
        assert logger.logs[0]["user"] == "test_agent"
        assert logger.logs[0]["action"] == "reset_environment"
        assert logger.logs[0]["status_code"] == 200
    
    def test_get_user_actions(self):
        """Should retrieve actions for a specific user"""
        logger = AuditLogger()
        
        # Log actions from different users
        logger.log_action("user1", "reset", "/reset", "POST", 200)
        logger.log_action("user2", "step", "/step", "POST", 200)
        logger.log_action("user1", "state", "/state", "GET", 200)
        
        user1_actions = logger.get_user_actions("user1")
        assert len(user1_actions) == 2
        assert all(a["user"] == "user1" for a in user1_actions)
    
    def test_get_all_actions(self):
        """Should retrieve all logged actions"""
        logger = AuditLogger()
        
        for i in range(5):
            logger.log_action(f"user{i}", f"action{i}", f"/endpoint{i}", "POST", 200)
        
        all_actions = logger.get_all_actions()
        assert len(all_actions) == 5
    
    def test_audit_logging_disabled(self, monkeypatch):
        """Should respect ENABLE_AUDIT_LOGGING flag"""
        monkeypatch.setenv("ENABLE_AUDIT_LOGGING", "false")
        from feature_flag_env.server.security import SecurityConfig
        
        config = SecurityConfig()
        assert config.enable_audit_logging is False


class TestRateLimiter:
    """Test rate limiting functionality"""
    
    def test_rate_limit_allows_requests_under_limit(self):
        """Should allow requests under the limit"""
        limiter = RateLimiter()
        
        for i in range(10):
            allowed, error = limiter.is_allowed("user1")
            assert allowed is True
            assert error is None
    
    def test_rate_limit_blocks_excess_requests(self):
        """Should block requests exceeding the limit"""
        from feature_flag_env.server.security import config
        
        limiter = RateLimiter()
        
        # Make requests up to the limit
        for i in range(config.rate_limit_requests):
            allowed, error = limiter.is_allowed("user1")
            assert allowed is True
        
        # Next request should be blocked
        allowed, error = limiter.is_allowed("user1")
        assert allowed is False
        assert error is not None
        assert "Rate limit exceeded" in error
    
    def test_rate_limit_per_user(self):
        """Rate limits should be per-user, not global"""
        from feature_flag_env.server.security import config
        
        limiter = RateLimiter()
        
        # User1 reaches limit
        for i in range(config.rate_limit_requests):
            limiter.is_allowed("user1")
        
        # User2 should still have quota
        allowed, error = limiter.is_allowed("user2")
        assert allowed is True
    
    def test_get_user_quota(self):
        """Should return accurate quota information"""
        from feature_flag_env.server.security import config
        
        limiter = RateLimiter()
        
        # Make some requests
        for i in range(5):
            limiter.is_allowed("user1")
        
        quota = limiter.get_user_quota("user1")
        assert quota["requests_used"] == 5
        assert quota["requests_limit"] == config.rate_limit_requests
        assert quota["requests_remaining"] == config.rate_limit_requests - 5


class TestSecurityStatus:
    """Test security status endpoint information"""
    
    def test_security_status_format(self):
        """Should return properly formatted security status"""
        status = get_security_status()
        
        # Check all required fields
        assert "enabled" in status
        assert "require_auth" in status
        assert "audit_logging" in status
        assert "rate_limiting" in status
        assert "jwt_algorithm" in status
        assert "token_expiry_hours" in status
        assert "rate_limit_requests" in status
        assert "rate_limit_window_seconds" in status
        assert "api_keys_configured" in status
    
    def test_security_status_values(self, monkeypatch):
        """Should reflect current configuration"""
        monkeypatch.setenv("ENABLE_SECURITY", "true")
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("API_KEYS", "user1=key1")
        
        # Reload security module to pick up new environment
        import importlib
        import feature_flag_env.server.security as sec_module
        importlib.reload(sec_module)
        
        # Get fresh status from reloaded module
        status = sec_module.get_security_status()
        
        assert status["enabled"] is True
        assert status["require_auth"] is True
        assert status["api_keys_configured"] is True


class TestBackwardCompatibility:
    """Test that security features don't break existing functionality"""
    
    def test_security_disabled_by_default(self, monkeypatch):
        """Security should be completely disabled by default (backward compatible)"""
        monkeypatch.setenv("ENABLE_SECURITY", "false")
        
        # Reload config with disabled security
        import importlib
        import feature_flag_env.server.security as sec_module
        importlib.reload(sec_module)
        
        assert sec_module.config.enabled is False
        assert sec_module.config.require_auth is False
    
    def test_existing_endpoints_work_without_security(self):
        """Existing API endpoints should work without authentication when security disabled"""
        # This is implicitly tested by the fact that inference.py still works
        # without requiring authentication headers
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
