"""Wrapper entry point for OpenEnv validator at repository root.

This forwards to the actual app implementation in feature-flag-agent-env/server/app.py
so that the openenv validator running from the repo root can find server.app:app and main().
"""

import os
import sys
from pathlib import Path

# Ensure we can import from feature-flag-agent-env
_project_root = Path(__file__).resolve().parents[1] / "feature-flag-agent-env"
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import and re-export the actual app from the nested implementation package.
from feature_flag_env.server.app import app  # noqa: F401

__all__ = ["app", "main"]


def main():
    """Entry point for running the server via `openenv serve` or `[project.scripts]`."""
    import uvicorn
    
    host = os.getenv("ENV_HOST", "0.0.0.0")
    port = int(os.getenv("ENV_PORT", os.getenv("PORT", "7860")))
    reload = os.getenv("ENV_RELOAD", "false").lower() == "true"

    uvicorn.run(
        "server.app:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()


