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

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from contextlib import asynccontextmanager
import uvicorn
import os

# Import our environment and models
from feature_flag_env.server.feature_flag_environment import FeatureFlagEnvironment
from feature_flag_env.models import (
    FeatureFlagAction,
    FeatureFlagObservation,
    FeatureFlagState,
    StepResponse,
    ResetResponse
)


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
    print("🌍 Environment initialized on server startup")
    yield
    # Shutdown: Cleanup if needed
    print("🛑 Server shutting down")
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
# REQUEST/RESPONSE MODELS (for API)
# =========================
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
        
        print(f"🔄 Episode reset - New episode started")
        print(f"   Feature: {observation.feature_name}")
        print(f"   Initial rollout: {observation.current_rollout_percentage}%")
        
        return ResetResponse(
            observation=observation,
            info={
                "episode_id": environment.state().episode_id,
                "scenario_name": environment.state().scenario_name,
                "difficulty": environment.state().difficulty,
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
        # ✅ Pydantic validates action_type automatically via Literal type
        # ✅ Pydantic validates target_percentage via Field(ge=0, le=100)
        # No manual validation needed for these fields!
        
        # Create FeatureFlagAction from validated request
        action = FeatureFlagAction(
            action_type=action_request.action_type,
            target_percentage=action_request.target_percentage,
            reason=action_request.reason
        )
        
        # Execute step in environment
        response = environment.step(action)
        
        print(f"⏩ Step executed: {action.action_type} → {action.target_percentage}%")
        print(f"   Reward: {response.reward:+.2f}")
        print(f"   Errors: {response.observation.error_rate*100:.2f}%")
        print(f"   Done: {response.done}")
        
        return response
    
    except HTTPException:
        # Re-raise HTTP exceptions (already have proper status codes)
        raise
    
    except ValueError as e:
        # Handle environment-specific errors (e.g., episode done)
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    
    except Exception as e:
        # Handle unexpected errors - log and return 500
        import traceback
        print(f"❌ Unexpected error in /step: {e}")
        print(traceback.format_exc())
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
# MAIN ENTRY POINT
# =========================
if __name__ == "__main__":
    """
    Run the server directly with:
    python feature_flag_env/server/app.py
    
    Or with uvicorn:
    uvicorn feature_flag_env.server.app:app --host 0.0.0.0 --port 8000
    """
    # Get configuration from environment variables
    host = os.getenv("ENV_HOST", "0.0.0.0")
    port = int(os.getenv("ENV_PORT", "8000"))
    reload = os.getenv("ENV_RELOAD", "false").lower() == "true"
    
    print(f"🚀 Starting Feature Flag Environment Server")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Docs: http://localhost:{port}/docs")
    print(f"   Health: http://localhost:{port}/health")
    
    uvicorn.run(
        "feature_flag_env.server.app:app",
        host=host,
        port=port,
        reload=reload
    )