"""
API Authentication & Security Feature Guide

Comprehensive guide for using the new API Authentication & Security module
in the Feature Flag Agent Environment.

This feature is OPTIONAL and DISABLED BY DEFAULT for full backward compatibility.
"""

# =============================================================================
#  QUICK START - SECURITY DISABLED (DEFAULT)
# =============================================================================

🚀 By default, security is completely disabled:
- ✅ All existing codes work unchanged
- ✅ No authentication required
- ✅ No rate limiting
- ✅ No behavior changes
- ✅ Full backward compatibility

To verify security is disabled:
```bash
cd feature-flag-agent-env
python -c "from feature_flag_env.server.security import config; print(f'Security enabled: {config.enabled}')"
# Output: Security enabled: False
```


# =============================================================================
#  ENABLE SECURITY (ENTERPRISE MODE)
# =============================================================================

To enable API authentication, audit logging, and rate limiting:

1. Set ENABLE_SECURITY=true in .env:

   ENABLE_SECURITY=true
   REQUIRE_AUTH=false          # Start with auth disabled for gentle migration
   JWT_SECRET=your-super-secret-key-change-in-production
   API_KEYS=agent1=key1,agent2=key2,agent3=key3


2. Restart the server:

   python -m feature_flag_env.server.app


3. Verify security is enabled:

   GET http://localhost:8000/security/status
   
   Response:
   {
     "enabled": true,
     "require_auth": false,
     "audit_logging": true,
     "rate_limiting": true,
     "rate_limit_requests": 100,
     "rate_limit_window_seconds": 60,
     ...
   }


# =============================================================================
#  FEATURE 1: JWT TOKEN AUTHENTICATION
# =============================================================================

Create tokens for service-to-service communication:

1. Generate a token:

   POST /security/token
   {
     "username": "agent1",
     "hours": 24
   }
   
   Response:
   {
     "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
     "expires_at": "2025-01-15T10:30:00",
     "token_type": "Bearer"
   }


2. Use the token to authenticate requests:

   GET /health
   Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...


Example with Python:

   import requests
   
   # Generate token
   response = requests.post(
       "http://localhost:8000/security/token",
       json={"username": "agent1", "hours": 24}
   )
   token = response.json()["token"]
   
   # Use token in authenticated requests
   headers = {"Authorization": f"Bearer {token}"}
   
   result = requests.get(
       "http://localhost:8000/health",
       headers=headers
   )
   print(result.json())


# =============================================================================
#  FEATURE 2: API KEY AUTHENTICATION
# =============================================================================

Use API keys for simpler authentication (vs tokens):

1. Configure API keys in .env:

   API_KEYS=agent1=secret-key-123,agent2=secret-key-456,agent3=secret-key-789


2. Use API key in requests:

   GET /health
   X-API-Key: secret-key-123


Example with Python:

   import requests
   
   headers = {"X-API-Key": "secret-key-123"}
   
   result = requests.get(
       "http://localhost:8000/health",
       headers=headers
   )
   print(result.json())


Example with curl:

   curl -H "X-API-Key: secret-key-123" http://localhost:8000/health


# =============================================================================
#  FEATURE 3: RATE LIMITING
# =============================================================================

Prevent API abuse with automatic rate limiting:

Configuration (in .env):

   ENABLE_RATE_LIMITING=true
   RATE_LIMIT_REQUESTS=100           # max requests per window
   RATE_LIMIT_WINDOW_SECONDS=60      # time window in seconds
   
   # Result: 100 requests per 60 seconds per user/API key


Check your current quota:

   GET /security/quota
   X-API-Key: secret-key-123
   
   Response:
   {
     "requests_used": 42,
     "requests_limit": 100,
     "window_seconds": 60,
     "requests_remaining": 58
   }


Example behavior:

   # Exceed rate limit
   for i in range(150):
       response = requests.get(
           "http://localhost:8000/health",
           headers={"X-API-Key": "agent1"}
       )
       if response.status_code == 429:
           print(f"Rate limited! {response.json()['detail']}")
           break


# =============================================================================
#  FEATURE 4: AUDIT LOGGING
# =============================================================================

Track all API access for compliance and debugging:

Configuration (in .env):

   ENABLE_AUDIT_LOGGING=true         # Logs all API actions
   AUDIT_ENCRYPTION=false            # Optional: encrypt audit logs


View your action history:

   GET /security/audit/actions?limit=50
   X-API-Key: secret-key-123
   
   Response:
   {
     "user": "agent1",
     "total": 42,
     "actions": [
       {
         "timestamp": "2025-01-14T10:30:45.123456",
         "user": "agent1",
         "action": "reset",
         "endpoint": "/reset",
         "method": "POST",
         "status_code": 200,
         "details": {}
       },
       {
         "timestamp": "2025-01-14T10:30:46.456789",
         "user": "agent1",
         "action": "step",
         "endpoint": "/step",
         "method": "POST",
         "status_code": 200,
         "details": {}
       }
     ]
   }


Audit logs are persisted to files:

   logs/audit/audit_20250114.log    # Daily audit log file
   logs/audit/audit_20250115.log


Each log entry includes:
- Timestamp (ISO format)
- User/API key
- Action performed
- Endpoint hit
- HTTP method
- Response status code
- Additional context


# =============================================================================
#  COMPLETE CONFIGURATION EXAMPLES
# =============================================================================

Example 1: Development (No Security)
──────────────────────────────────────

.env:
   ENABLE_SECURITY=false
   ENV_HOST=0.0.0.0
   ENV_PORT=8000


Usage:
   # No authentication needed
   curl http://localhost:8000/health
   curl -X POST http://localhost:8000/reset


Example 2: Staging (Audit Only, No Auth)
──────────────────────────────────────────

.env:
   ENABLE_SECURITY=true
   REQUIRE_AUTH=false               # No auth required yet
   ENABLE_AUDIT_LOGGING=true
   ENABLE_RATE_LIMITING=false       # No rate limits
   ENV_PORT=8001


Usage:
   # No auth needed, but all actions are logged
   curl http://localhost:8001/health
   
   # Check logs
   curl http://localhost:8001/security/audit/actions


Example 3: Production (Full Security)
──────────────────────────────────────

.env:
   ENABLE_SECURITY=true
   REQUIRE_AUTH=true                # Authentication required
   JWT_SECRET=your-production-secret-key-min-32-chars
   API_KEYS=agent1=prod-key-1,agent2=prod-key-2
   ENABLE_RATE_LIMITING=true
   RATE_LIMIT_REQUESTS=1000
   RATE_LIMIT_WINDOW_SECONDS=60
   ENABLE_AUDIT_LOGGING=true
   ENV_PORT=8000
   ENV_HOST=0.0.0.0


Usage:
   # Generate token for agent
   curl -X POST http://localhost:8000/security/token \
     -H "Content-Type: application/json" \
     -d '{"username": "agent1", "hours": 24}'
   
   # Use token to authenticate
   TOKEN=$(curl -X POST http://localhost:8000/security/token \
     -H "Content-Type: application/json" \
     -d '{"username": "agent1"}' | jq -r '.token')
   
   curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/health
   
   # Check quota
   curl -H "X-API-Key: prod-key-1" http://localhost:8000/security/quota
   
   # View audit trail
   curl -H "X-API-Key: prod-key-1" http://localhost:8000/security/audit/actions


Example 4: Kubernetes Deployment (K8s Secrets)
────────────────────────────────────────────────

apiVersion: v1
kind: ConfigMap
metadata:
  name: feature-flag-env-config
data:
  .env: |
    ENABLE_SECURITY=true
    REQUIRE_AUTH=true
    ENABLE_RATE_LIMITING=true
    ENABLE_AUDIT_LOGGING=true
    JWT_ALGORITHM=HS256
    TOKEN_EXPIRY_HOURS=24
    RATE_LIMIT_REQUESTS=1000
    RATE_LIMIT_WINDOW_SECONDS=60


---
apiVersion: v1
kind: Secret
metadata:
  name: feature-flag-env-secrets
type: Opaque
stringData:
  JWT_SECRET: your-kubernetes-managed-secret
  API_KEYS: agent1=prod-key-1,agent2=prod-key-2


---
apiVersion: v1
kind: Pod
metadata:
  name: feature-flag-env
spec:
  containers:
  - name: server
    image: feature-flag-env:latest
    ports:
    - containerPort: 8000
    envFrom:
    - configMapRef:
        name: feature-flag-env-config
    - secretRef:
        name: feature-flag-env-secrets
    volumeMounts:
    - name: audit-logs
      mountPath: /app/logs/audit
  volumes:
  - name: audit-logs
    emptyDir: {}


# =============================================================================
#  MIGRATION GUIDE: FROM NO SECURITY TO FULL SECURITY
# =============================================================================

Step 1: (Now) Production = ENABLE_SECURITY=false (current)
         Development = ENABLE_SECURITY=false (current)


Step 2: (Week 1) Enable audit logging without auth
        
        .env:
          ENABLE_SECURITY=true
          REQUIRE_AUTH=false
          ENABLE_AUDIT_LOGGING=true
        
        ✅ All existing code works unchanged
        ✅ Start tracking API usage
        ✅ Identify which agents access which endpoints


Step 3: (Week 2) Add rate limiting without auth
        
        .env:
          ENABLE_RATE_LIMITING=true
          RATE_LIMIT_REQUESTS=10000      # High limit, won't affect anyone
        
        ✅ Existing code works unchanged
        ✅ Start monitoring rate limit behavior
        ✅ Adjust limits based on actual usage


Step 4: (Week 3) Create tokens for new agents
        
        POST /security/token {"username": "new_agent", "hours": 72}
        
        ✅ New agents can use tokens
        ✅ Existing agents still work without auth


Step 5: (Week 4) Enable auth, migrate existing agents
        
        .env:
          REQUIRE_AUTH=true
        
        Migrate agents:
        - Generate tokens for each agent
        - Update agent code to include Authorization header
        - Test in staging first


Step 6: (Week 5) Lower rate limits to realistic values
        
        .env:
          RATE_LIMIT_REQUESTS=100
          RATE_LIMIT_WINDOW_SECONDS=60
        
        ✅ Prevents abuse
        ✅ Fair usage policy enforced


# =============================================================================
#  TROUBLESHOOTING
# =============================================================================

Q: My existing code broke after enabling security!
A: Set REQUIRE_AUTH=false in .env. Security is now enabled but not required yet.
   Your existing code will work, and you can migrate requests to use tokens/keys
   on a flexible timeline.


Q: How do I disable security if I enabled it accidentally?
A: Set ENABLE_SECURITY=false in .env and restart the server.
   All existing endpoints will work immediately.


Q: My rate limit is too low for my use case
A: Adjust in .env:
   RATE_LIMIT_REQUESTS=10000        # Increase limit
   RATE_LIMIT_WINDOW_SECONDS=60     # Or increase window


Q: How do I reset/revoke an API key?
A: Currently, you must restart the server with updated API_KEYS in .env.
   Future version: Dynamic key management endpoint.


Q: Where are audit logs stored?
A: In logs/audit/ directory:
   - logs/audit/audit_20250114.log
   - logs/audit/audit_20250115.log
   One file per day, appended to automatically.


Q: Can I encrypt audit logs?
A: Yes! Set AUDIT_ENCRYPTION=true in .env.
   Logs will be encrypted before writing to disk.


Q: How do I extract audit logs for analysis?
A: Audit logs are JSON format, one entry per line:
   cat logs/audit/audit_20250114.log | jq '.'
   
   Or use /security/audit/actions endpoint to query programmatically:
   curl http://localhost:8000/security/audit/actions?limit=1000


# =============================================================================
#  SECURITY BEST PRACTICES
# =============================================================================

1. CHANGE JWT_SECRET IN PRODUCTION
   
   ❌ DON'T:     JWT_SECRET=your-super-secret-key-change-in-production
   ✅ DO:        JWT_SECRET=<generate-strong-random-string>
   
   Generate with:
   python -c "import secrets; print(secrets.token_urlsafe(32))"


2. USE STRONG API KEYS
   
   ❌ DON'T:     API_KEYS=agent1=123456
   ✅ DO:        API_KEYS=agent1=<64-char-random-string>
   
   Generate with:
   python -c "import secrets; print(secrets.token_urlsafe(48))"


3. ROTATE SECRETS REGULARLY
   
   Update API_KEYS and JWT_SECRET periodically (e.g., monthly)
   Create new tokens before rotating


4. USE SHORT TOKEN EXPIRY IN PRODUCTION
   
   ✅ TOKEN_EXPIRY_HOURS=1         # Tokens expire quickly
   ✅ TOKEN_EXPIRY_HOURS=24        # For trusted internal services


5. MONITOR AUDIT LOGS
   
   Regularly check logs/audit/ for suspicious activity:
   - Repeated 401/403 errors (possible attacks)
   - 429 rate limit hits (possible DOS)
   - Unusual access patterns


6. ENABLE RATE LIMITING
   
   Always enable in production to prevent abuse:
   ENABLE_RATE_LIMITING=true
   RATE_LIMIT_REQUESTS=100         # Adjust based on usage


7. BACKUP AUDIT LOGS
   
   Audit logs are important for compliance:
   - Daily backup to S3/storage
   - Archive for 1 year minimum


# =============================================================================
#  INTEGRATION EXAMPLES
# =============================================================================

Python Agent with JWT:
────────────────────

import requests
import json
from datetime import datetime

class SecureAgent:
    def __init__(self, server_url, username):
        self.server_url = server_url
        self.username = username
        self.token = None
        self.token_expires = None
    
    def get_token(self):
        """Generate new token if needed"""
        if self.token is None or datetime.utcnow() > self.token_expires:
            response = requests.post(
                f"{self.server_url}/security/token",
                json={"username": self.username, "hours": 12}
            )
            data = response.json()
            self.token = data["token"]
            self.token_expires = datetime.fromisoformat(
                data["expires_at"]
            )
        return self.token
    
    def reset_episode(self):
        """Reset with authentication"""
        token = self.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(
            f"{self.server_url}/reset",
            headers=headers
        )
        return response.json()
    
    def step(self, action):
        """Take a step with authentication"""
        token = self.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(
            f"{self.server_url}/step",
            headers=headers,
            json=action
        )
        return response.json()


# Usage:
agent = SecureAgent("http://localhost:8000", "my_agent")
observation = agent.reset_episode()
result = agent.step({
    "action_type": "INCREASE_ROLLOUT",
    "target_percentage": 30
})
print(result)


Docker Deployment with Security:
─────────────────────────────────

FROM python:3.11

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY feature_flag_env/ feature_flag_env/

ENV ENABLE_SECURITY=true
ENV REQUIRE_AUTH=true
ENV JWT_SECRET=${JWT_SECRET_BUILD_ARG}
ENV API_KEYS=${API_KEYS_BUILD_ARG}

EXPOSE 8000

CMD ["python", "-m", "feature_flag_env.server.app"]


Build and run:

docker build \
  --build-arg JWT_SECRET_BUILD_ARG=$(python -c "import secrets; print(secrets.token_urlsafe(32))") \
  --build-arg API_KEYS_BUILD_ARG="agent1=key1,agent2=key2" \
  -t feature-flag-env:latest .

docker run \
  -e ENABLE_SECURITY=true \
  -e REQUIRE_AUTH=true \
  -e JWT_SECRET=${JWT_SECRET} \
  -e API_KEYS="agent1=key1,agent2=key2" \
  -p 8000:8000 \
  feature-flag-env:latest


# =============================================================================
#  ADDITIONAL RESOURCES
# =============================================================================

- Security module: feature_flag_env/server/security.py
- Security tests: tests/test_security.py
- Server integration: feature_flag_env/server/app.py
- Configuration: .env

For questions or issues:
- Check troubleshooting section above
- Review test examples in tests/test_security.py
- Check audit logs in logs/audit/
"""
