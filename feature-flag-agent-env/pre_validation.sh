#!/usr/bin/env bash
# =============================================================================
# pre_validation.sh
# 
# Automated checklist for Meta OpenEnv Hackathon submission.
# Run this BEFORE submitting to catch issues early.
# 
# Usage: ./pre_validation.sh
# =============================================================================

set +e  # Exit on error

echo "============================================================"
echo "🔍 FEATURE FLAG AGENT - PRE-VALIDATION CHECKLIST"
echo "============================================================"
echo ""

PASS_COUNT=0
FAIL_COUNT=0

# Helper function to check pass/fail
check_result() {
    if [ $1 -eq 0 ]; then
        echo "✅ PASSED: $2"
        PASS_COUNT=$((PASS_COUNT+1))
    else
        echo "❌ FAILED: $2"
        FAIL_COUNT=$((FAIL_COUNT+1))
    fi
}

# =============================================================================
# CHECK 1: Required Files Exist
# =============================================================================
echo "📁 Checking required files..."

test -f "openenv.yaml"
check_result $? "openenv.yaml exists"

test -f "inference.py"
check_result $? "inference.py exists"

test -f "README.md"
check_result $? "README.md exists"

test -f "pyproject.toml"
check_result $? "pyproject.toml exists"

test -f ".gitignore"
check_result $? ".gitignore exists"

echo ""

# =============================================================================
# CHECK 2: OpenEnv Spec Compliance
# =============================================================================
echo "📋 Checking OpenEnv spec compliance..."

grep -q "env_class:" openenv.yaml
check_result $? "env_class defined in openenv.yaml"

grep -q "action_type:" openenv.yaml
check_result $? "action_type defined in openenv.yaml"

grep -q "observation_type:" openenv.yaml
check_result $? "observation_type defined in openenv.yaml"

grep -q "state_type:" openenv.yaml
check_result $? "state_type defined in openenv.yaml"

echo ""

# =============================================================================
# CHECK 3: Python Environment
# =============================================================================
echo "🐍 Checking Python environment..."

python --version > /dev/null 2>&1
check_result $? "Python is installed"

python -c "import pydantic" > /dev/null 2>&1
check_result $? "pydantic is installed"

python -c "import fastapi" > /dev/null 2>&1
check_result $? "fastapi is installed"

python -c "import uvicorn" > /dev/null 2>&1
check_result $? "uvicorn is installed"

echo ""

# =============================================================================
# CHECK 4: Run Inference Script
# =============================================================================
echo "🧪 Testing inference.py..."

timeout 60 python inference.py --agent baseline --episodes 1 > /tmp/inference_test.log 2>&1
check_result $? "inference.py runs successfully"

echo ""

# =============================================================================
# CHECK 5: Environment Variables
# =============================================================================
echo "🔐 Checking environment configuration..."

if [ -z "$GROQ_API_KEY" ]; then
    echo "⚠️  WARNING: GROQ_API_KEY not set (LLM agent won't work)"
else
    echo "✅ PASSED: GROQ_API_KEY is set"
    PASS_COUNT=$((PASS_COUNT+1))
fi

if [ -z "$HF_TOKEN" ]; then
    echo "⚠️  WARNING: HF_TOKEN not set (HF Spaces won't work)"
else
    echo "✅ PASSED: HF_TOKEN is set"
    PASS_COUNT=$((PASS_COUNT+1))
fi

echo ""

# =============================================================================
# CHECK 6: Tasks & Graders
# =============================================================================
echo "🎯 Checking tasks and graders..."

test -f "feature_flag_env/tasks/graders.py"
check_result $? "graders.py exists"

python -c "from feature_flag_env.tasks.graders import Task1Grader, Task2Grader, Task3Grader" > /dev/null 2>&1
check_result $? "All 3 graders can be imported"

echo ""

# =============================================================================
# CHECK 7: Server Can Start
# =============================================================================
echo "🚀 Checking if server can start..."

timeout 5 python feature_flag_env/server/app.py > /tmp/server_test.log 2>&1 || true
grep -q "Uvicorn running" /tmp/server_test.log 2>/dev/null
check_result $? "Server starts successfully"

echo ""

# =============================================================================
# FINAL SUMMARY
# =============================================================================
echo "============================================================"
echo "📊 VALIDATION SUMMARY"
echo "============================================================"
echo "   Passed: $PASS_COUNT"
echo "   Failed: $FAIL_COUNT"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo "✅ ALL CRITICAL CHECKS PASSED!"
    echo ""
    echo "Your submission is ready!"
    echo ""
    echo "Next steps:"
    echo "1. Push to Hugging Face Space"
    echo "2. Verify Space is accessible"
    echo "3. Submit your hackathon entry"
    echo "4. Good luck! 🚀"
    exit 0
else
    echo "❌ SOME CHECKS FAILED!"
    echo ""
    echo "Please fix the failed checks before submitting."
    echo "Run ./pre_validation.sh again after fixing."
    exit 1
fi