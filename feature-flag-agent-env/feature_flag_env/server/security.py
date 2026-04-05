"""
feature_flag_env/server/security.py

API Authentication & Security Module

Provides:
- JWT token generation and validation
- API key authentication
- Rate limiting
- Audit logging per user
- Optional enforcement (all features disabled by default unless explicitly enabled)

Security is fully opt-in: set ENABLE_SECURITY=true in .env to activate
"""

import os
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from functools import wraps
from collections import defaultdict
import logging

try:
    from jwt import encode, decode, ExpiredSignatureError, InvalidTokenError
except ImportError:
    raise ImportError(
        "PyJWT not installed. Install with: pip install PyJWT>=2.8.0"
    )

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

try:
    from feature_flag_env.utils.database import database
    DATABASE_AVAILABLE = True
except Exception:
    database = None
    DATABASE_AVAILABLE = False


# =========================
# LOGGING SETUP
# =========================
logger = logging.getLogger(__name__)


# =========================
# CONFIGURATION
# =========================
class SecurityConfig:
    """Security configuration loaded from environment variables"""
    
    def __init__(self):
        # Feature flags
        self.enabled = os.getenv("ENABLE_SECURITY", "false").lower() == "true"
        # Backward compatibility: auth cannot be required when security is disabled.
        self.require_auth = self.enabled and os.getenv("REQUIRE_AUTH", "false").lower() == "true"
        self.enable_audit_logging = os.getenv("ENABLE_AUDIT_LOGGING", "true").lower() == "true"
        self.enable_rate_limiting = os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "true"
        
        # JWT Configuration
        self.jwt_secret = os.getenv("JWT_SECRET", "your-super-secret-key-change-in-production")
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.token_expiry_hours = int(os.getenv("TOKEN_EXPIRY_HOURS", "24"))
        
        # Rate Limiting Configuration
        self.rate_limit_requests = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
        self.rate_limit_window_seconds = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
        
        # API Keys (comma-separated: user1=key1,user2=key2)
        self.api_keys = self._parse_api_keys(
            os.getenv("API_KEYS", "")
        )
        
        # Encryption key for audit logs (optional)
        self.audit_encryption_enabled = os.getenv("AUDIT_ENCRYPTION", "false").lower() == "true"
    
    def _parse_api_keys(self, api_keys_str: str) -> Dict[str, str]:
        """Parse API keys from comma-separated format: user1=key1,user2=key2"""
        if not api_keys_str:
            return {}
        
        keys = {}
        for pair in api_keys_str.split(","):
            if "=" in pair:
                username, key = pair.split("=", 1)
                keys[username.strip()] = key.strip()
        
        return keys


config = SecurityConfig()


# =========================
# AUDIT LOGGING
# =========================
class AuditLogger:
    """Centralized audit logging for compliance and debugging"""
    
    def __init__(self):
        self.logs: List[Dict] = []
        self._ensure_audit_directory()
    
    def _ensure_audit_directory(self):
        """Create audit logs directory if it doesn't exist"""
        os.makedirs("logs/audit", exist_ok=True)
    
    def log_action(
        self,
        user: str,
        action: str,
        endpoint: str,
        method: str,
        status_code: int,
        details: Optional[Dict] = None
    ):
        """
        Log an API action for audit trail.
        
        Args:
            user: Username or API key
            action: Description (e.g., "reset_environment", "step_environment")
            endpoint: URL path (e.g., "/reset", "/step")
            method: HTTP method (e.g., "POST", "GET")
            status_code: HTTP response code
            details: Additional context
        """
        if not config.enable_audit_logging:
            return
        
        timestamp = datetime.utcnow().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "user": user,
            "action": action,
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "details": details or {}
        }
        
        self.logs.append(log_entry)
        
        # Optionally persist to file
        self._write_audit_file(log_entry)

        # Optionally persist to SQLite (best-effort)
        if DATABASE_AVAILABLE and database and database.is_enabled():
            database.record_audit_event(
                ts=timestamp,
                user=user,
                action=action,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                details=details or {},
            )
        
        logger.info(f"[AUDIT] {user} → {action} ({method} {endpoint}) → {status_code}")
    
    def _write_audit_file(self, log_entry: Dict):
        """Write audit log entry to file"""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d")
            audit_file = f"logs/audit/audit_{timestamp}.log"
            
            with open(audit_file, "a") as f:
                f.write(f"{log_entry}\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def get_user_actions(self, user: str, limit: int = 100) -> List[Dict]:
        """Get recent actions for a specific user"""
        return [log for log in self.logs if log["user"] == user][-limit:]
    
    def get_all_actions(self, limit: int = 100) -> List[Dict]:
        """Get all recent actions"""
        return self.logs[-limit:]


# Global audit logger instance
audit_logger = AuditLogger()


# =========================
# RATE LIMITING
# =========================
class RateLimiter:
    """Track API usage per user and enforce rate limits"""
    
    def __init__(self):
        self.usage: Dict[str, List[float]] = defaultdict(list)
    
    def is_allowed(self, user: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user can make a request.
        
        Returns:
            (is_allowed: bool, error_message: Optional[str])
        """
        if not config.enable_rate_limiting:
            return True, None
        
        now = time.time()
        window_start = now - config.rate_limit_window_seconds
        
        # Clean old requests outside the window
        self.usage[user] = [
            req_time for req_time in self.usage[user]
            if req_time > window_start
        ]
        
        # Check if user exceeded limit
        if len(self.usage[user]) >= config.rate_limit_requests:
            return False, (
                f"Rate limit exceeded: {config.rate_limit_requests} requests "
                f"per {config.rate_limit_window_seconds} seconds"
            )
        
        # Record this request
        self.usage[user].append(now)
        return True, None
    
    def get_user_quota(self, user: str) -> Dict[str, int]:
        """Get quota info for a user"""
        now = time.time()
        window_start = now - config.rate_limit_window_seconds
        
        active_requests = len([
            t for t in self.usage[user]
            if t > window_start
        ])
        
        return {
            "requests_used": active_requests,
            "requests_limit": config.rate_limit_requests,
            "window_seconds": config.rate_limit_window_seconds,
            "requests_remaining": max(0, config.rate_limit_requests - active_requests)
        }


# Global rate limiter instance
rate_limiter = RateLimiter()


# =========================
# JWT TOKEN MANAGEMENT
# =========================
def create_token(username: str, hours: Optional[int] = None) -> str:
    """
    Create a JWT token for a user.
    
    Args:
        username: The username to encode
        hours: Token expiry in hours (defaults to config.token_expiry_hours)
    
    Returns:
        JWT token string
    """
    hours = hours or config.token_expiry_hours
    expires = datetime.utcnow() + timedelta(hours=hours)
    
    payload = {
        "sub": username,
        "exp": expires,
        "iat": datetime.utcnow()
    }
    
    token = encode(
        payload,
        config.jwt_secret,
        algorithm=config.jwt_algorithm
    )
    
    return token


def verify_token(token: str) -> Dict:
    """
    Verify a JWT token and return the payload.
    
    Args:
        token: JWT token string
    
    Returns:
        Token payload (dict with 'sub' = username)
    
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = decode(
            token,
            config.jwt_secret,
            algorithms=[config.jwt_algorithm]
        )
        return payload
    
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired"
        )
    
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}"
        )


def verify_api_key(api_key: str) -> str:
    """
    Verify an API key and return the associated username.
    
    Args:
        api_key: The API key to verify
    
    Returns:
        Username associated with the key
    
    Raises:
        HTTPException: If API key is invalid
    """
    for username, key in config.api_keys.items():
        if key == api_key:
            return username
    
    raise HTTPException(
        status_code=401,
        detail="Invalid API key"
    )


# =========================
# AUTHENTICATION HELPERS
# =========================
def extract_token(request: Request) -> Optional[str]:
    """
    Extract JWT token from request headers.
    
    Expected format: "Authorization: Bearer <token>"
    """
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header:
        return None
    
    parts = auth_header.split()
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Use: 'Bearer <token>'"
        )
    
    return parts[1]


def extract_api_key(request: Request) -> Optional[str]:
    """
    Extract API key from request headers.
    
    Expected format: "X-API-Key: <key>"
    """
    return request.headers.get("X-API-Key")


async def get_authenticated_user(request: Request) -> str:
    """
    Extract and verify the authenticated user from request.
    
    Supports two authentication methods:
    1. JWT token in Authorization header: "Bearer <token>"
    2. API key in X-API-Key header
    
    If security is disabled, returns "anonymous".
    
    Returns:
        Username of authenticated user
    
    Raises:
        HTTPException: If authentication fails
    """
    if not config.enabled or not config.require_auth:
        return "anonymous"
    
    # Try JWT token first
    token = extract_token(request)
    if token:
        payload = verify_token(token)
        return payload.get("sub", "unknown")
    
    # Try API key
    api_key = extract_api_key(request)
    if api_key:
        return verify_api_key(api_key)
    
    # No valid auth provided
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Use 'Authorization: Bearer <token>' or 'X-API-Key: <key>'"
    )


# =========================
# MIDDLEWARE
# =========================
class SecurityMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for security enforcement.
    
    Handles:
    - Authentication verification
    - Rate limiting checks
    - Audit logging of all requests
    """
    
    async def dispatch(self, request: Request, call_next):
        """Process request through security checks"""
        
        # Get user (or "anonymous" if auth disabled/not required)
        try:
            user = await get_authenticated_user(request)
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        
        # Check rate limit
        if config.enabled and config.enable_rate_limiting:
            allowed, error_msg = rate_limiter.is_allowed(user)
            if not allowed:
                audit_logger.log_action(
                    user=user,
                    action="rate_limit_exceeded",
                    endpoint=request.url.path,
                    method=request.method,
                    status_code=429,
                    details={"error": error_msg}
                )
                
                return JSONResponse(status_code=429, content={"detail": error_msg})
        
        # Process request
        response = await call_next(request)
        
        # Log action
        audit_logger.log_action(
            user=user,
            action=request.url.path.lstrip("/"),
            endpoint=request.url.path,
            method=request.method,
            status_code=response.status_code
        )
        
        # Add security headers to response
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


# =========================
# ENDPOINT DECORATORS
# =========================
def require_auth(func):
    """
    Decorator to require authentication on an endpoint.
    
    If security is disabled, allows all access.
    If security is enabled, requires valid JWT or API key.
    """
    @wraps(func)
    async def wrapper(*args, request: Request, **kwargs):
        user = await get_authenticated_user(request)
        return await func(*args, request=request, user=user, **kwargs)
    
    return wrapper


def rate_limit_check(func):
    """
    Decorator to enforce rate limiting on an endpoint.
    """
    @wraps(func)
    async def wrapper(*args, request: Request, user: str = "anonymous", **kwargs):
        if config.enabled and config.enable_rate_limiting:
            allowed, error_msg = rate_limiter.is_allowed(user)
            if not allowed:
                raise HTTPException(status_code=429, detail=error_msg)
        
        return await func(*args, request=request, user=user, **kwargs)
    
    return wrapper


# =========================
# UTILITY FUNCTIONS
# =========================
def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for secure storage.
    
    Use this to hash keys before storing in environment variables.
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_security_status() -> Dict:
    """Get current security configuration status"""
    return {
        "enabled": config.enabled,
        "require_auth": config.require_auth,
        "audit_logging": config.enable_audit_logging,
        "rate_limiting": config.enable_rate_limiting,
        "jwt_algorithm": config.jwt_algorithm,
        "token_expiry_hours": config.token_expiry_hours,
        "rate_limit_requests": config.rate_limit_requests,
        "rate_limit_window_seconds": config.rate_limit_window_seconds,
        "api_keys_configured": len(config.api_keys) > 0,
    }
