"""Module path bridge for OpenEnv validators running from repository root.

The actual feature_flag_env implementation is at:
  feature-flag-agent-env/feature_flag_env/

This __init__.py ensures that when imports like 'feature_flag_env.server.feature_flag_environment'
are resolved, they look in the nested location by adding it to sys.path.
"""

import sys
from pathlib import Path

# Ensure the nested feature-flag-agent-env directory is in the Python path
# This allows imports like "from feature_flag_env.server import app" to work
# when the actual code is at feature-flag-agent-env/feature_flag_env/
_FEATURE_FLAG_ENV_ROOT = Path(__file__).resolve().parents[1] / "feature-flag-agent-env"

if _FEATURE_FLAG_ENV_ROOT.is_dir():
    _path_str = str(_FEATURE_FLAG_ENV_ROOT)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)
