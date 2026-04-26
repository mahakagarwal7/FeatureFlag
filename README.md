---
title: Feature Flag Simulation
emoji: 🚀
colorFrom: blue
colorTo: red
sdk: docker
app_port: 7860
---

# 🚀 FeatureFlag-Agent-Env

**AI-Powered Intelligent Feature Rollout & Risk Management Simulation**

An OpenEnv-compliant simulation environment where AI agents learn to safely rollout features at scale.

---

## 🎮 Action Space

| Action             | Description                    |
| ------------------ | ------------------------------ |
| `INCREASE_ROLLOUT` | Increase deployment percentage |
| `DECREASE_ROLLOUT` | Decrease deployment percentage |
| `MAINTAIN`         | Keep current percentage        |
| `HALT_ROLLOUT`     | Pause rollout temporarily      |
| `FULL_ROLLOUT`     | Deploy to 100% immediately     |
| `ROLLBACK`         | Emergency revert to 0%         |

---

## 📊 Observation Space

| Field                        | Type  | Description                |
| ---------------------------- | ----- | -------------------------- |
| `current_rollout_percentage` | float | Current rollout %          |
| `error_rate`                 | float | Error rate (0.0-1.0)       |
| `latency_p99_ms`             | float | P99 latency in ms          |
| `user_adoption_rate`         | float | User adoption %            |
| `revenue_impact`             | float | Revenue in dollars         |
| `system_health_score`        | float | Composite health (0.0-1.0) |

---

## 🚀 Quick Start

```bash
# Install dependencies
pip install -e .

# Run baseline inference
python inference.py --agent baseline --episodes 3

# Start server
python -m feature_flag_env.server.app
```

---

## Connect To Hugging Face

Use your existing .env token with provider mode set to Hugging Face:

```bash
LLM_PROVIDER=hf
HF_API_BASE_URL=https://router.huggingface.co/v1
MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
```

Run an LLM episode test:

```bash
python inference.py --agent llm --episodes 1
```

---

## Deploy To Hugging Face Spaces

Deployment guide:

- See DEPLOY_TO_HUGGINGFACE.md

PowerShell quick deploy:

```powershell
./scripts/deploy_to_hf.ps1 -SpaceId "your-username/feature-flag-ai"
```
