#!/bin/bash
# validation_suite.sh - Run after bug fixes

set -e  # Exit on first error
echo "🔍 Running Final Validation Suite..."

cd feature-flag-agent-env

# 1. Import sanity check
echo -e "\n[1/6] Testing imports..."
python -c "
from feature_flag_env.server.feature_flag_environment import make_environment
from agents.llm_agent import LLMAgent
from feature_flag_env.utils.database import DatabaseManager
from feature_flag_env.utils.monitoring import MonitoringManager
print('✅ All critical imports successful')
"

# 2. Environment factory test
echo -e "\n[2/6] Testing environment factory..."
python -c "
from feature_flag_env.server.feature_flag_environment import make_environment
env = make_environment({'task_name': 'task1'})
obs = env.reset()
assert hasattr(obs, 'current_rollout_percentage')
print('✅ Environment factory works')
"
# 3. Baseline inference test
echo -e "\n[3/6] Running baseline inference..."
python inference.py --agent baseline --episodes 1 --task task1 --local 2>&1 | grep -q "\[END\]" && echo "✅ Baseline inference passed"
# 4. Server health check
echo -e "\n[4/6] Testing server startup..."
python -m uvicorn feature_flag_env.server.app:app --host 127.0.0.1 --port 8002 &
SERVER_PID=$!
sleep 5
curl -sf http://127.0.0.1:8002/health > /dev/null && echo "✅ Server health endpoint OK"
kill $SERVER_PID 2>/dev/null || true
# 5. Database initialization test
echo -e "\n[5/6] Testing database init..."
python -c "
from feature_flag_env.utils.database import DatabaseManager
from fastapi import FastAPI
app = FastAPI()
db = DatabaseManager.get_instance()
db.init_app(app)
import os
os.makedirs('logs', exist_ok=True)
# Try a dummy write
import sqlite3
conn = sqlite3.connect(db.db_path, timeout=db.timeout)
conn.execute('CREATE TABLE IF NOT EXISTS test (id INTEGER)')
conn.close()
print('✅ Database initialization works')
"
# 6. LLM agent fallback test
echo -e "\n[6/6] Testing LLM agent fallback..."
python -c "
import os
os.environ['LLM_PROVIDER'] = 'groq'
# Don't set GROQ_API_KEY to trigger fallback
from agents.llm_agent import LLMAgent
agent = LLMAgent()
assert agent.use_baseline == True, 'Should fallback without API key.'
print('✅ LLM agent fallback works correctly')
"
echo -e "\n🎉 All validation checks passed!"
echo "✅ Repository is ready for submission/testing."
