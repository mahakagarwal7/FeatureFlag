#!/usr/bin/env python3
"""Test script to verify database initialization during server startup."""

import subprocess
import time
import os
import json
import pathlib
import urllib.request
import sys

# Set database enabled
env = os.environ.copy()
env['ENABLE_DATABASE'] = 'true'

# Start server
print("Starting server...")
p = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'feature_flag_env.server.app:app', 
     '--host', '127.0.0.1', '--port', '8002', '--log-level', 'critical'],
    cwd=os.getcwd(),
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Wait for startup
time.sleep(5)

try:
    # Check health endpoint
    health_resp = json.load(urllib.request.urlopen('http://127.0.0.1:8002/health'))
    print(f"✓ Health endpoint responded: {health_resp.get('status')}")
    
    # Check if database file was created
    db_path = pathlib.Path('logs/app.db')
    if db_path.is_file():
        size = db_path.stat().st_size
        print(f"✓ Database file created: {db_path} ({size} bytes)")
    else:
        print(f"✗ Database file NOT created: {db_path}")
        sys.exit(1)
    
    print("\n✅ Database initialization test PASSED")
    
except Exception as e:
    print(f"✗ Test failed: {e}")
    sys.exit(1)
finally:
    p.terminate()
    p.wait()
