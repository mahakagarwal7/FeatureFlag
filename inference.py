"""Repository-root inference entrypoint.

Delegates execution to feature-flag-agent-env/inference.py so validators that
run from repository root can still find and execute the required script name.
"""

import runpy
from pathlib import Path

TARGET = Path(__file__).resolve().parent / "feature-flag-agent-env" / "inference.py"

if __name__ == "__main__":
    runpy.run_path(str(TARGET), run_name="__main__")
