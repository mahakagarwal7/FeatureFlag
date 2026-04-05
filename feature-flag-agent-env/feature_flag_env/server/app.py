"""
feature_flag_env/server/app.py

FastAPI Server for OpenEnv-Compliant Feature Flag Environment

This server exposes the environment via HTTP endpoints:
- POST /reset    → Start a new episode
- POST /step     → Execute an action
- GET  /state    → Get current episode state
- GET  /health   → Health check endpoint

This allows agents (LLM, baseline, etc.) to interact with the
environment remotely, which is required for OpenEnv specification.
"""

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from contextlib import asynccontextmanager
import uvicorn
import os
import sys
import time
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv not installed; .env file will not be loaded")

# Import our environment and models
try:
    from feature_flag_env.server.feature_flag_environment import FeatureFlagEnvironment
    from feature_flag_env.models import (
        FeatureFlagAction,
        FeatureFlagObservation,
        FeatureFlagState,
        StepResponse,
        ResetResponse
    )
except ModuleNotFoundError:
    # Support direct execution: `python feature_flag_env/server/app.py`
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from feature_flag_env.server.feature_flag_environment import FeatureFlagEnvironment
    from feature_flag_env.models import (
        FeatureFlagAction,
        FeatureFlagObservation,
        FeatureFlagState,
        StepResponse,
        ResetResponse
    )


# Import security module (optional, non-breaking)
try:
    from feature_flag_env.server.security import (
        SecurityMiddleware,
        config as security_config,
        create_token,
        verify_token,
        audit_logger,
        rate_limiter,
        get_security_status,
        get_authenticated_user,
    )
    SECURITY_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Security module not available: {e}")
    logger.info("Server will run without API authentication/audit features")
    SECURITY_AVAILABLE = False


# Import monitoring module (optional, non-breaking)
try:
    from feature_flag_env.utils.monitoring import (
        MetricsCollector,
        AlertManager,
        metrics,
        get_prometheus_metrics,
        get_dashboard_data,
        get_status_summary,
        record_step as monitoring_record_step,
        record_api_call,
    )
    from feature_flag_env.utils.monitoring import MonitoringConfig
    MONITORING_AVAILABLE = True
    monitoring_config = MonitoringConfig()
except ImportError as e:
    logger.warning(f"Monitoring module not available: {e}")
    logger.info("Server will run without monitoring/alerting features")
    MONITORING_AVAILABLE = False
    monitoring_config = None


# Import database module (optional, non-breaking)
try:
    from feature_flag_env.utils.database import database
    DATABASE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Database module not available: {e}")
    logger.info("Server will run without SQLite persistence")
    DATABASE_AVAILABLE = False
    database = None


# =========================
# FASTAPI APP INITIALIZATION
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup/shutdown events.
    Replaces deprecated @app.on_event("startup")
    """
    # Startup: Initialize environment
    global environment
    environment = FeatureFlagEnvironment()
    print("[*] Environment initialized on server startup")
    yield
    # Shutdown: Cleanup if needed
    print("[!] Server shutting down")
    environment = None


app = FastAPI(
    title="Feature Flag Agent Environment",
    description="OpenEnv-compliant simulation for AI-powered feature rollout",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,  # ✅ Use lifespan instead of on_event
)

# Global environment instance (one per server)
environment: Optional[FeatureFlagEnvironment] = None


# =========================
# SECURITY MIDDLEWARE (optional)
# =========================
if SECURITY_AVAILABLE and security_config.enabled:
    app.add_middleware(SecurityMiddleware)
    logger.info("[+] Security middleware ENABLED (authentication, rate limiting, audit logging)")
else:
    if SECURITY_AVAILABLE:
        logger.info("[-] Security module available but DISABLED (set ENABLE_SECURITY=true to activate)")
    else:
        logger.info("[-] Security module not installed (install: pip install PyJWT>=2.8.0 python-jose[cryptography]>=3.0.0)")


# =========================
# MONITORING MIDDLEWARE (optional)
# =========================
if MONITORING_AVAILABLE and monitoring_config.enabled:
    @app.middleware("http")
    async def monitoring_middleware(request: Request, call_next):
        start_time = time.time()
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            record_api_call(
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                duration_ms=duration_ms,
                user="anonymous"
            )
            return response
        except Exception:
            duration_ms = (time.time() - start_time) * 1000
            record_api_call(
                endpoint=request.url.path,
                method=request.method,
                status_code=500,
                duration_ms=duration_ms,
                user="anonymous"
            )
            raise
    logger.info("[*] Monitoring middleware ENABLED (metrics collection, health tracking, alerting)")
else:
    if MONITORING_AVAILABLE:
        logger.info("⚪ Monitoring module available but DISABLED (set ENABLE_MONITORING=true to activate)")
    else:
        logger.info("⚪ Monitoring module not installed (install: pip install prometheus-client>=0.19.0)")


class StepRequest(BaseModel):
    """
    Request model for /step endpoint.
    
    ✅ FIXED: Use Literal type to restrict valid action types at model level.
    This provides automatic validation - invalid action_type returns HTTP 422.
    """
    action_type: Literal[
        "INCREASE_ROLLOUT",
        "DECREASE_ROLLOUT",
        "MAINTAIN",
        "HALT_ROLLOUT",
        "FULL_ROLLOUT",
        "ROLLBACK"
    ] = Field(..., description="Type of action to take")
    
    target_percentage: float = Field(
        ..., 
        ge=0.0, 
        le=100.0, 
        description="Target rollout percentage (0-100)"
    )
    
    reason: str = Field(
        default="", 
        max_length=500, 
        description="Agent's reasoning for this action"
    )


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    environment_ready: bool
    message: str


# =========================
# ENDPOINTS
# =========================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Used by:
    - Load balancers to check if server is alive
    - Hugging Face Spaces to verify deployment
    - Debugging to confirm server is running
    """
    global environment
    
    is_ready = environment is not None
    
    return HealthResponse(
        status="healthy" if is_ready else "unhealthy",
        environment_ready=is_ready,
        message="Server is running" if is_ready else "Environment not initialized"
    )


@app.post("/reset", response_model=ResetResponse)
async def reset_environment():
    """
    Start a new episode.
    
    This is called at the BEGINNING of each episode.
    It resets all state and returns the initial observation.
    """
    global environment
    
    if environment is None:
        raise HTTPException(
            status_code=500,
            detail="Environment not initialized"
        )
    
    try:
        observation = environment.reset()
        state = environment.state()

        if DATABASE_AVAILABLE and database and database.is_enabled():
            database.record_episode_reset(
                episode_id=state.episode_id,
                scenario_name=state.scenario_name,
                difficulty=state.difficulty,
                feature_name=observation.feature_name,
                current_rollout_percentage=observation.current_rollout_percentage,
                error_rate=observation.error_rate,
                metadata={"source": "api_reset"},
            )
        
        print(f"🔄 Episode reset - New episode started")
        print(f"   Feature: {observation.feature_name}")
        print(f"   Initial rollout: {observation.current_rollout_percentage}%")
        
        return ResetResponse(
            observation=observation,
            info={
                "episode_id": state.episode_id,
                "scenario_name": state.scenario_name,
                "difficulty": state.difficulty,
            }
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Reset failed: {str(e)}"
        )


@app.post("/step", response_model=StepResponse)
async def step_environment(action_request: StepRequest):
    """
    Execute an action and return new observation + reward.
    
    This is the MAIN endpoint called every time the agent takes an action.
    
    ✅ FIXED: StepRequest now uses Literal type for action_type,
    so Pydantic automatically validates and returns HTTP 422 for invalid actions.
    """
    global environment

    if environment is None:
        raise HTTPException(
            status_code=500,
            detail="Environment not initialized"
        )

    try:
        action = FeatureFlagAction(
            action_type=action_request.action_type,
            target_percentage=action_request.target_percentage,
            reason=action_request.reason
        )

        response = environment.step(action)
        state = environment.state()

        print(f"⏩ Step executed: {action.action_type} → {action.target_percentage}%")
        print(f"   Reward: {response.reward:+.2f}")
        print(f"   Errors: {response.observation.error_rate*100:.2f}%")
        print(f"   Done: {response.done}")

        if DATABASE_AVAILABLE and database and database.is_enabled():
            database.record_step(
                episode_id=state.episode_id,
                step_count=state.step_count,
                action_type=action.action_type,
                target_percentage=action.target_percentage,
                reward=response.reward,
                error_rate=response.observation.error_rate,
                latency_p99_ms=response.observation.latency_p99_ms,
                system_health_score=response.observation.system_health_score,
                done=response.done,
                reason=action.reason,
                metadata={"source": "api_step"},
            )

        if MONITORING_AVAILABLE and monitoring_config.enabled:
            from time import time
            step_duration_ms = max(10, int((time() % 1000)))
            has_error = response.observation.error_rate > 0

            monitoring_record_step(
                step_duration_ms=step_duration_ms,
                action=action.action_type,
                error=has_error,
                user="anonymous"
            )

        return response

    except HTTPException:
        raise

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:
        import traceback
        print(f"❌ Unexpected error in /step: {e}")
        print(traceback.format_exc())
        if MONITORING_AVAILABLE and monitoring_config.enabled:
            monitoring_record_step(
                step_duration_ms=0,
                action="error",
                error=True,
                user="anonymous"
            )

        raise HTTPException(
            status_code=500,
            detail=f"Step failed: {str(e)}"
        )


@app.get("/state", response_model=FeatureFlagState)
async def get_state():
    """
    Get current episode state.
    
    This returns episode metadata (step count, total reward, history, etc.)
    Used for:
    - Logging
    - Grading
    - Debugging
    - RL training trajectories
    """
    global environment
    
    if environment is None:
        raise HTTPException(
            status_code=500,
            detail="Environment not initialized"
        )
    
    try:
        state = environment.state()
        return state
    
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@app.get("/info")
async def get_environment_info():
    """
    Get environment metadata.
    
    Returns information about the environment itself
    (not episode-specific).
    """
    return {
        "name": "FeatureFlag-Agent-Env",
        "version": "1.0.0",
        "description": "AI-Powered Feature Rollout & Risk Management Simulation",
        "action_space": [
            "INCREASE_ROLLOUT",
            "DECREASE_ROLLOUT",
            "MAINTAIN",
            "HALT_ROLLOUT",
            "FULL_ROLLOUT",
            "ROLLBACK"
        ],
        "observation_space": {
            "current_rollout_percentage": "float (0.0-100.0)",
            "error_rate": "float (0.0-1.0)",
            "latency_p99_ms": "float (ms)",
            "user_adoption_rate": "float (0.0-1.0)",
            "revenue_impact": "float (dollars)",
            "system_health_score": "float (0.0-1.0)",
            "active_users": "int",
            "feature_name": "string",
            "time_step": "int"
        },
        "max_steps": 50,
        "scenario_difficulties": ["easy", "medium", "hard"],
    }


# =========================
# SECURITY ENDPOINTS (optional)
# =========================
if SECURITY_AVAILABLE:
    """
    Security management endpoints for token creation, audit logs, and configuration.
    These endpoints only exist if the security module is available.
    """
    
    class TokenRequest(BaseModel):
        """Request model for token generation"""
        username: str = Field(..., description="Username to create token for")
        hours: Optional[int] = Field(None, description="Token expiry hours (defaults to config)")
    
    
    class TokenResponse(BaseModel):
        """Response model for token generation"""
        token: str
        expires_at: str
        token_type: str = "Bearer"
    
    
    class SecurityStatusResponse(BaseModel):
        """Response model for security status"""
        enabled: bool
        require_auth: bool
        audit_logging: bool
        rate_limiting: bool
        jwt_algorithm: str
        token_expiry_hours: int
        rate_limit_requests: int
        rate_limit_window_seconds: int
        api_keys_configured: bool
    
    
    @app.get("/security/status", response_model=SecurityStatusResponse)
    async def get_security_status_endpoint():
        """
        Get security configuration status.
        
        Useful for:
        - Verifying security is enabled
        - Getting rate limit thresholds
        - Checking authentication requirements
        - Enterprise deployment verification
        """
        if not security_config.enabled:
            raise HTTPException(
                status_code=403,
                detail="Security is not enabled"
            )
        
        return get_security_status()
    
    
    @app.post("/security/token", response_model=TokenResponse)
    async def create_token_endpoint(request: TokenRequest):
        """
        Create a JWT token for API access.
        
        Used for:
        - Enterprise deployments requiring authentication
        - Setting up service-to-service communication
        - Temporary access grants
        
        Example request body:
        {
            "username": "agent1",
            "hours": 24
        }
        """
        if not security_config.enabled:
            raise HTTPException(
                status_code=403,
                detail="Security is not enabled"
            )
        
        try:
            token = create_token(request.username, request.hours)
            hours = request.hours or security_config.token_expiry_hours
            
            from datetime import datetime, timedelta
            expires_at = (datetime.utcnow() + timedelta(hours=hours)).isoformat()
            
            audit_logger.log_action(
                user=request.username,
                action="token_created",
                endpoint="/security/token",
                method="POST",
                status_code=200
            )
            
            return TokenResponse(
                token=token,
                expires_at=expires_at
            )
        
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Token creation failed: {str(e)}"
            )
    
    
    @app.get("/security/audit/actions")
    async def get_audit_log(request: Request, limit: int = 100):
        """
        Get audit log of recent API actions.
        
        Requires:
        - Security to be enabled
        - Valid authentication (JWT or API key)
        
        Query parameters:
        - limit: Maximum number of actions to return (default: 100)
        """
        if not security_config.enabled:
            raise HTTPException(
                status_code=403,
                detail="Security is not enabled"
            )
        
        # Require authentication
        if security_config.require_auth:
            user = await get_authenticated_user(request)
        else:
            user = "anonymous"
        
        return {
            "user": user,
            "actions": audit_logger.get_user_actions(user, limit),
            "total": len(audit_logger.get_user_actions(user, limit))
        }
    
    
    @app.get("/security/quota")
    async def get_rate_limit_quota(request: Request):
        """
        Get current rate limit quota for the authenticated user.
        
        Returns:
        - requests_used: Number of requests made in current window
        - requests_limit: Maximum requests per window
        - window_seconds: Size of the time window in seconds
        - requests_remaining: Number of requests still allowed
        """
        if not security_config.enabled or not security_config.enable_rate_limiting:
            raise HTTPException(
                status_code=403,
                detail="Rate limiting is not enabled"
            )
        
        # Get user (or anonymous if auth not required)
        try:
            user = await get_authenticated_user(request)
        except:
            user = "anonymous"
        
        return rate_limiter.get_user_quota(user)


# =========================
# MONITORING ENDPOINTS (optional)
# =========================
if MONITORING_AVAILABLE:
    """
    Monitoring and alerting endpoints for observability.
    These endpoints provide:
    - Prometheus-compatible metrics export (/metrics)
    - Health status and dashboard data (/monitoring/health, /monitoring/dashboard)
    - Active alerts and warnings (/monitoring/alerts)
    """
    
    class HealthStatusResponse(BaseModel):
        """Health status response"""
        health_score: float = Field(..., ge=0.0, le=1.0, description="Overall health (0-1)")
        error_rate: float = Field(..., description="Error rate percentage")
        latency_p99_ms: float = Field(..., description="99th percentile latency in ms")
        uptime_seconds: float = Field(..., description="Server uptime in seconds")
        status: str = Field(..., description="Status: healthy/degraded/critical")
    
    
    class AlertResponse(BaseModel):
        """Alert information"""
        id: str
        severity: str  # "warning", "error", "critical"
        metric: str
        threshold: float
        current_value: float
        timestamp: str
        description: str
    
    
    @app.get("/metrics")
    async def prometheus_metrics():
        """
        Prometheus-compatible metrics endpoint.
        
        Used by:
        - Prometheus servers for time-series data collection
        - Grafana for dashboard visualization
        - Alertmanager for threshold-based alerting
        
        Returns metrics in Prometheus text format.
        """
        if not monitoring_config.enabled:
            raise HTTPException(
                status_code=403,
                detail="Monitoring is not enabled"
            )
        
        metrics_text = get_prometheus_metrics()
        return metrics_text
    
    
    @app.get("/monitoring/health", response_model=HealthStatusResponse)
    async def get_health_status():
        """
        Get current health status.
        
        Returns:
        - health_score: Overall system health (0-1)
        - error_rate: Percentage of errors
        - latency_p99_ms: 99th percentile latency
        - uptime_seconds: Time since server startup
        - status: One of [healthy, degraded, critical]
        """
        if not monitoring_config.enabled:
            raise HTTPException(
                status_code=403,
                detail="Monitoring is not enabled"
            )

        health = metrics.get_health_status()

        status = "healthy"
        if health.system_health_score < monitoring_config.health_score_threshold:
            status = "degraded"
        if health.error_rate > monitoring_config.error_rate_threshold:
            status = "critical"

        return HealthStatusResponse(
            health_score=health.system_health_score,
            error_rate=health.error_rate,
            latency_p99_ms=health.avg_latency_ms,
            uptime_seconds=health.uptime_seconds,
            status=status
        )
    
    
    @app.get("/monitoring/dashboard")
    async def get_monitoring_dashboard():
        """
        Get complete dashboard data.
        
        Returns:
        - summary: Health status and high-level metrics
        - metrics: Detailed metrics per category
        - alerts: Active alerts and warnings
        - recommendations: Suggestions based on current state
        
        Used by:
        - Web dashboards for real-time visualization
        - Admin tools for system overview
        - Alerting systems for decision making
        """
        if not monitoring_config.enabled:
            raise HTTPException(
                status_code=403,
                detail="Monitoring is not enabled"
            )
        
        return get_dashboard_data()
    
    
    @app.get("/monitoring/alerts")
    async def get_active_alerts():
        """
        Get list of active alerts and warnings.
        
        Returns:
        - alerts: List of triggered alerts
        - count: Number of active alerts
        - critical_count: Number of critical alerts
        - warning_count: Number of warning-level alerts
        """
        if not monitoring_config.enabled:
            raise HTTPException(
                status_code=403,
                detail="Monitoring is not enabled"
            )
        
        # Get alerts from the monitoring system
        from feature_flag_env.utils.monitoring import MetricsCollector, AlertManager
        metrics = MetricsCollector()
        alert_mgr = AlertManager()
        
        health = metrics.get_health_status()
        current_metrics = {metric: metrics.get_metric_stats(metric) for metric in ['latency', 'error_rate']}
        
        alerts = alert_mgr.check_alerts(health, current_metrics)
        
        return {
            "alerts": [
                {
                    "id": alert.id,
                    "severity": alert.severity,
                    "metric": alert.metric,
                    "threshold": alert.threshold,
                    "current_value": alert.current_value,
                    "timestamp": alert.timestamp.isoformat(),
                    "description": alert.description
                }
                for alert in alerts
            ],
            "count": len(alerts),
            "critical_count": len([a for a in alerts if a.severity == "critical"]),
            "warning_count": len([a for a in alerts if a.severity == "warning"])
        }


# =========================
# DATABASE ENDPOINTS (optional)
# =========================
if DATABASE_AVAILABLE:
    @app.get("/db/health")
    async def get_database_health():
        """Get SQLite health/status (safe even when DB disabled)."""
        return database.get_health()


    @app.get("/db/stats")
    async def get_database_stats():
        """Get SQLite row counts for episode and audit events."""
        return database.get_stats()


if __name__ == "__main__":
    """
    Run the server directly with:
    python -m feature_flag_env.server.app

    Or with uvicorn:
    uvicorn feature_flag_env.server.app:app --host 0.0.0.0 --port 8000
    """
    host = os.getenv("ENV_HOST", "0.0.0.0")
    port = int(os.getenv("ENV_PORT", "8000"))
    reload = os.getenv("ENV_RELOAD", "false").lower() == "true"

    print(f"🚀 Starting Feature Flag Environment Server")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Docs: http://localhost:{port}/docs")
    print(f"   Health: http://localhost:{port}/health")

    if SECURITY_AVAILABLE:
        status = get_security_status()
        if security_config.enabled:
            print(f"   🔒 Security: ENABLED")
            print(f"      - Authentication: {'ON' if security_config.require_auth else 'OFF'}")
            print(f"      - Rate Limiting: {status['rate_limit_requests']} req/{status['rate_limit_window_seconds']}s")
            print(f"      - Audit Logging: ON")
        else:
            print(f"   ⚪ Security: Available but disabled (set ENABLE_SECURITY=true to enable)")

    if MONITORING_AVAILABLE:
        if monitoring_config.enabled:
            print(f"   [*] Monitoring: ENABLED")
            print(f"      - Metrics Collection: ON")
            print(f"      - Alerting: {'ON' if monitoring_config.enable_alerting else 'OFF'}")
            print(f"      - Prometheus Export: {'ON' if monitoring_config.enable_prometheus else 'OFF'}")
            print(f"      - Dashboard: http://localhost:{port}/monitoring/dashboard")
            print(f"      - Prometheus: http://localhost:{port}/metrics")
        else:
            print(f"   ⚪ Monitoring: Available but disabled (set ENABLE_MONITORING=true to enable)")

    if DATABASE_AVAILABLE and database:
        db_health = database.get_health()
        if db_health.get("enabled"):
            print(f"   🗄️ SQLite: ENABLED")
            print(f"      - Path: {db_health.get('path')}")
            print(f"      - Connected: {'YES' if db_health.get('connected') else 'NO'}")
            print(f"      - DB Health: http://localhost:{port}/db/health")
            print(f"      - DB Stats: http://localhost:{port}/db/stats")
        else:
            print(f"   ⚪ SQLite: Available but disabled (set ENABLE_DATABASE=true to enable)")

    uvicorn.run(
        "feature_flag_env.server.app:app",
        host=host,
        port=port,
        reload=reload
    )