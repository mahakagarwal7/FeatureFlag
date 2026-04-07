#!/usr/bin/env bash
# validate-submission.sh — OpenEnv submission validator for this repo.

set -uo pipefail

DOCKER_BUILD_TIMEOUT="${DOCKER_BUILD_TIMEOUT:-600}"
if [ -t 1 ]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  BOLD='\033[1m'
  NC='\033[0m'
else
  RED='' GREEN='' YELLOW='' BOLD='' NC=''
fi

run_with_timeout() {
  local secs="$1"; shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$secs" "$@"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$secs" "$@"
  else
    "$@" &
    local pid=$!
    ( sleep "$secs" && kill "$pid" 2>/dev/null ) &
    local watcher=$!
    wait "$pid" 2>/dev/null
    local rc=$?
    kill "$watcher" 2>/dev/null
    wait "$watcher" 2>/dev/null
    return "$rc"
  fi
}

portable_mktemp() {
  local prefix="${1:-validate}"
  mktemp "${TMPDIR:-/tmp}/${prefix}-XXXXXX" 2>/dev/null || mktemp
}

CLEANUP_FILES=()
cleanup() { rm -f "${CLEANUP_FILES[@]+${CLEANUP_FILES[@]}}"; }
trap cleanup EXIT

load_env_var_from_file() {
  local key="$1"
  local file="$2"
  if [ -f "$file" ] && [ -z "${!key:-}" ]; then
    local value
    value=$(grep -E "^${key}=" "$file" | tail -n 1 | cut -d'=' -f2- | tr -d '\r')
    if [ -n "$value" ]; then
      export "$key=$value"
    fi
  fi
}

is_placeholder_value() {
  local value="${1:-}"
  local lower
  lower=$(printf "%s" "$value" | tr '[:upper:]' '[:lower:]')
  case "$lower" in
    your_*|*token_here*|*api_key_here*|*local_image_name*|*change_me*|*placeholder*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

find_project_dir() {
  local repo="$1"
  if [ -f "$repo/openenv.yaml" ]; then
    printf "%s" "$repo"
    return 0
  fi
  if [ -f "$repo/feature-flag-agent-env/openenv.yaml" ]; then
    printf "%s" "$repo/feature-flag-agent-env"
    return 0
  fi
  return 1
}

PING_URL="${1:-}"
REPO_DIR="${2:-.}"

if [ -z "$PING_URL" ]; then
  printf "Usage: %s <ping_url> [repo_dir]\n" "$0"
  printf "\n"
  printf "  ping_url   Your HuggingFace Space URL (e.g. https://your-space.hf.space)\n"
  printf "  repo_dir   Path to your repo (default: current directory)\n"
  exit 1
fi

if ! REPO_DIR="$(cd "$REPO_DIR" 2>/dev/null && pwd)"; then
  printf "Error: directory '%s' not found\n" "${2:-.}"
  exit 1
fi

if ! PROJECT_DIR="$(find_project_dir "$REPO_DIR")"; then
  printf "Error: openenv.yaml not found in %s or %s/feature-flag-agent-env\n" "$REPO_DIR" "$REPO_DIR"
  exit 1
fi

load_env_var_from_file API_BASE_URL "$PROJECT_DIR/.env"
load_env_var_from_file MODEL_NAME "$PROJECT_DIR/.env"
load_env_var_from_file HF_TOKEN "$PROJECT_DIR/.env"
load_env_var_from_file LOCAL_IMAGE_NAME "$PROJECT_DIR/.env"
load_env_var_from_file API_BASE_URL "$PROJECT_DIR/.env.example"
load_env_var_from_file MODEL_NAME "$PROJECT_DIR/.env.example"
load_env_var_from_file HF_TOKEN "$PROJECT_DIR/.env.example"
load_env_var_from_file LOCAL_IMAGE_NAME "$PROJECT_DIR/.env.example"

PING_URL="${PING_URL%/}"
PASS=0

log()  { printf "[%s] %b\n" "$(date -u +%H:%M:%S)" "$*"; }
pass() { log "${GREEN}PASSED${NC} -- $1"; PASS=$((PASS + 1)); }
fail() { log "${RED}FAILED${NC} -- $1"; }
hint() { printf "  ${YELLOW}Hint:${NC} %b\n" "$1"; }
stop_at() {
  printf "\n"
  printf "${RED}${BOLD}Validation stopped at %s.${NC} Fix the above before continuing.\n" "$1"
  exit 1
}

printf "\n"
printf "${BOLD}========================================${NC}\n"
printf "${BOLD}  OpenEnv Submission Validator${NC}\n"
printf "${BOLD}========================================${NC}\n"
log "Repo:        $REPO_DIR"
log "Project dir: $PROJECT_DIR"
log "Ping URL:    $PING_URL"
printf "\n"

log "${BOLD}Step 0/4: Checking required environment variables${NC} ..."

MISSING_ENV=0
for key in API_BASE_URL MODEL_NAME HF_TOKEN LOCAL_IMAGE_NAME; do
  if [ -z "${!key:-}" ]; then
    fail "$key is not set"
    MISSING_ENV=1
  elif is_placeholder_value "${!key}"; then
    fail "$key looks like a placeholder value"
    MISSING_ENV=1
  else
    pass "$key is set"
  fi
done

if [ "$MISSING_ENV" -ne 0 ]; then
  hint "Set missing variables in $PROJECT_DIR/.env or your shell environment."
  stop_at "Step 0"
fi

log "${BOLD}Step 1/4: Pinging HF Space${NC} ($PING_URL/reset) ..."

CURL_OUTPUT=$(portable_mktemp "validate-curl")
CLEANUP_FILES+=("$CURL_OUTPUT")
HTTP_CODE=$(curl -s -o "$CURL_OUTPUT" -w "%{http_code}" -X POST \
  -H "Content-Type: application/json" -d '{}' \
  "$PING_URL/reset" --max-time 30 2>/dev/null || printf "000")

if [ "$HTTP_CODE" = "401" ] && [ -n "${HF_TOKEN:-}" ]; then
  HTTP_CODE=$(curl -s -o "$CURL_OUTPUT" -w "%{http_code}" -X POST \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $HF_TOKEN" \
    -d '{}' "$PING_URL/reset" --max-time 30 2>/dev/null || printf "000")
fi

if [ "$HTTP_CODE" = "200" ]; then
  pass "HF Space is live and responds to /reset"
elif [ "$HTTP_CODE" = "000" ]; then
  fail "HF Space not reachable (connection failed or timed out)"
  hint "Check your network connection and that the Space is running."
  hint "Try: curl -s -o /dev/null -w '%{http_code}' -X POST $PING_URL/reset"
  stop_at "Step 1"
else
  fail "HF Space /reset returned HTTP $HTTP_CODE (expected 200)"
  if [ "$HTTP_CODE" = "401" ]; then
    hint "The Space requires authorization. Ensure HF_TOKEN is valid and has access to this Space."
  fi
  hint "Make sure your Space is running and the URL is correct."
  hint "Try opening $PING_URL in your browser first."
  stop_at "Step 1"
fi

log "${BOLD}Step 2/4: Running docker build${NC} ..."

if ! command -v docker >/dev/null 2>&1; then
  fail "docker command not found"
  hint "Install Docker: https://docs.docker.com/get-docker/"
  stop_at "Step 2"
fi

if [ -f "$PROJECT_DIR/Dockerfile" ]; then
  DOCKER_CONTEXT="$PROJECT_DIR"
elif [ -f "$PROJECT_DIR/server/Dockerfile" ]; then
  DOCKER_CONTEXT="$PROJECT_DIR/server"
else
  fail "No Dockerfile found in project root or server/ directory"
  stop_at "Step 2"
fi

log "  Found Dockerfile in $DOCKER_CONTEXT"

BUILD_OK=false
BUILD_OUTPUT=$(run_with_timeout "$DOCKER_BUILD_TIMEOUT" docker build "$DOCKER_CONTEXT" 2>&1) && BUILD_OK=true

if [ "$BUILD_OK" = true ]; then
  pass "Docker build succeeded"
else
  fail "Docker build failed (timeout=${DOCKER_BUILD_TIMEOUT}s)"
  printf "%s\n" "$BUILD_OUTPUT" | tail -20
  stop_at "Step 2"
fi

log "${BOLD}Step 3/4: Running openenv validate${NC} ..."

if ! command -v openenv >/dev/null 2>&1; then
  fail "openenv command not found"
  hint "Install it: pip install openenv-core"
  stop_at "Step 3"
fi

VALIDATE_OK=false
VALIDATE_OUTPUT=$(cd "$PROJECT_DIR" && openenv validate 2>&1) && VALIDATE_OK=true

if [ "$VALIDATE_OK" = true ]; then
  pass "openenv validate passed"
  [ -n "$VALIDATE_OUTPUT" ] && log "  $VALIDATE_OUTPUT"
else
  fail "openenv validate failed"
  printf "%s\n" "$VALIDATE_OUTPUT"
  stop_at "Step 3"
fi

printf "\n"
printf "${BOLD}========================================${NC}\n"
printf "${GREEN}${BOLD}  All %s/4 checks passed!${NC}\n" "$PASS"
printf "${GREEN}${BOLD}  Your submission is ready to submit.${NC}\n"
printf "${BOLD}========================================${NC}\n"
printf "\n"

exit 0
