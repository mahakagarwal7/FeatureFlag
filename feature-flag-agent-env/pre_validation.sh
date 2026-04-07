#!/usr/bin/env bash
# Automated pre-submission checklist for OpenEnv submission.

set +e

# Read required vars from .env/.env.example without sourcing (avoids CRLF parser issues).
load_env_var_from_file() {
  local key="$1"
  local file="$2"
  if [ -f "$file" ]; then
    local value
    value=$(grep -E "^${key}=" "$file" | tail -n 1 | cut -d'=' -f2- | tr -d '\r')
    if [ -n "$value" ] && [ -z "${!key:-}" ]; then
      export "$key=$value"
    fi
  fi
}

for required_key in API_BASE_URL MODEL_NAME HF_TOKEN; do
  load_env_var_from_file "$required_key" ".env"
  load_env_var_from_file "$required_key" ".env.example"
done

python_cmd_ok() {
  local cmd="$1"
  if [ "$cmd" = "py -3" ]; then
    py -3 -c "import pydantic, fastapi, uvicorn" >/dev/null 2>&1
  else
    "$cmd" -c "import pydantic, fastapi, uvicorn" >/dev/null 2>&1
  fi
}

PYTHON_BIN=""
if [ -n "${PYTHON_BIN_OVERRIDE:-}" ]; then
  PYTHON_BIN="$PYTHON_BIN_OVERRIDE"
elif command -v python >/dev/null 2>&1 && python_cmd_ok "python"; then
  PYTHON_BIN="python"
elif command -v py >/dev/null 2>&1 && python_cmd_ok "py -3"; then
  PYTHON_BIN="py -3"
elif command -v python3 >/dev/null 2>&1 && python_cmd_ok "python3"; then
  PYTHON_BIN="python3"
elif [ -x "/mnt/c/Users/Mahak/AppData/Local/Programs/Python/Python313/python.exe" ]; then
  PYTHON_BIN="/mnt/c/Users/Mahak/AppData/Local/Programs/Python/Python313/python.exe"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif command -v py >/dev/null 2>&1; then
  PYTHON_BIN="py -3"
else
  PYTHON_BIN="python3"
fi

run_python() {
  if [ "$PYTHON_BIN" = "py -3" ]; then
    py -3 "$@"
  else
    "$PYTHON_BIN" "$@"
  fi
}

PASS_COUNT=0
FAIL_COUNT=0

check_result() {
  if [ "$1" -eq 0 ]; then
    echo "PASS: $2"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "FAIL: $2"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

echo "============================================================"
echo "FEATURE FLAG AGENT - PRE-VALIDATION CHECKLIST"
echo "============================================================"

# Check 1: required files
test -f "openenv.yaml"; check_result $? "openenv.yaml exists"
test -f "inference.py"; check_result $? "inference.py exists"
test -f "README.md"; check_result $? "README.md exists"
test -f "pyproject.toml"; check_result $? "pyproject.toml exists"
test -f ".gitignore"; check_result $? ".gitignore exists"

# Check 2: OpenEnv spec
grep -q "env_class:" openenv.yaml; check_result $? "env_class declared"
grep -q "action_type:" openenv.yaml; check_result $? "action_type declared"
grep -q "observation_type:" openenv.yaml; check_result $? "observation_type declared"
grep -q "state_type:" openenv.yaml; check_result $? "state_type declared"

# Check 3: Python/runtime
run_python --version >/dev/null 2>&1; check_result $? "python runtime available"
run_python -c "import pydantic" >/dev/null 2>&1; check_result $? "pydantic import works"
run_python -c "import fastapi" >/dev/null 2>&1; check_result $? "fastapi import works"
run_python -c "import uvicorn" >/dev/null 2>&1; check_result $? "uvicorn import works"

# Check 4: inference runtime + structured logs
if [ "$PYTHON_BIN" = "py -3" ]; then
  timeout 120 py -3 inference.py --agent baseline --episodes 1 >/tmp/inference_test.log 2>&1
else
  timeout 120 "$PYTHON_BIN" inference.py --agent baseline --episodes 1 >/tmp/inference_test.log 2>&1
fi
check_result $? "inference.py baseline run succeeds"

grep -q "^\[START\]" /tmp/inference_test.log; check_result $? "[START] log emitted"
grep -q "^\[STEP\]" /tmp/inference_test.log; check_result $? "[STEP] log emitted"
grep -q "^\[END\]" /tmp/inference_test.log; check_result $? "[END] log emitted"

# Check 5: required environment variables
if [ -z "$API_BASE_URL" ]; then
  echo "FAIL: API_BASE_URL is not set"
  FAIL_COUNT=$((FAIL_COUNT + 1))
else
  echo "PASS: API_BASE_URL is set"
  PASS_COUNT=$((PASS_COUNT + 1))
fi

if [ -z "$MODEL_NAME" ]; then
  echo "FAIL: MODEL_NAME is not set"
  FAIL_COUNT=$((FAIL_COUNT + 1))
else
  echo "PASS: MODEL_NAME is set"
  PASS_COUNT=$((PASS_COUNT + 1))
fi

if [ -z "$HF_TOKEN" ]; then
  echo "FAIL: HF_TOKEN is not set"
  FAIL_COUNT=$((FAIL_COUNT + 1))
else
  echo "PASS: HF_TOKEN is set"
  PASS_COUNT=$((PASS_COUNT + 1))
fi

# Check 6: tasks and grader score range
test -f "feature_flag_env/tasks/graders.py"; check_result $? "graders.py exists"
run_python -c "from feature_flag_env.tasks.graders import Task1Grader, Task2Grader, Task3Grader" >/dev/null 2>&1
check_result $? "all three grader classes import"

run_python - <<'PY'
from agents.baseline_agent import BaselineAgent
from feature_flag_env.tasks.task1_safe_rollout import make_task1_environment
from feature_flag_env.tasks.task2_risk_aware import make_task2_environment
from feature_flag_env.tasks.task3_multi_objective import make_task3_environment
from feature_flag_env.tasks.graders import get_grader

tasks = [
    ("task1", make_task1_environment),
    ("task2", make_task2_environment),
    ("task3", make_task3_environment),
]

for name, maker in tasks:
    env = maker()
    agent = BaselineAgent()
    obs = env.reset()
    history = []
    trajectory = []
    done = False
    steps = 0
    while not done and steps < 60:
        action = agent.decide(obs, history)
        response = env.step(action)
        obs = response.observation
        done = response.done
        trajectory.append({"observation": obs, "action": action, "reward": response.reward})
        history.append({"obs": obs, "action": action, "reward": response.reward})
        steps += 1
    score = get_grader(name).grade(trajectory)
    if not (0.0 <= score <= 1.0):
        raise SystemExit(f"score out of range for {name}: {score}")
print("grader-range-ok")
PY
check_result $? "all task grader scores within [0.0,1.0]"

# Check 7: server startup probe
if [ "$PYTHON_BIN" = "py -3" ]; then
  timeout 15 py -3 feature_flag_env/server/app.py >/tmp/server_test.log 2>&1 || true
else
  timeout 15 "$PYTHON_BIN" feature_flag_env/server/app.py >/tmp/server_test.log 2>&1 || true
fi
if grep -Eq "Uvicorn running|Application startup complete|Started server process" /tmp/server_test.log; then
  check_result 0 "server starts"
else
  check_result 1 "server starts"
fi

echo "============================================================"
echo "VALIDATION SUMMARY"
echo "============================================================"
echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"

if [ "$FAIL_COUNT" -eq 0 ]; then
  echo "PASS: all critical checks passed"
  exit 0
fi

echo "FAIL: one or more checks failed"
exit 1
