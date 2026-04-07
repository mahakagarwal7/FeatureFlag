"""
server/app.py — OpenEnv-expected entry point.

This shim re-exports the FastAPI ``app`` instance from the canonical location
(feature_flag_env.server.app) so that ``openenv validate`` and the various
deployment modes (``openenv serve``, ``uv run``, ``python -m server.app``)
can discover the application at the standard ``server.app:app`` path.
"""

import uvicorn
import os

from feature_flag_env.server.app import app  # noqa: F401

__all__ = ["app"]


def main():
    """Entry point for running the server via `openenv serve` or `[project.scripts]`."""
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
