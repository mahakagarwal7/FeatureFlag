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

## 🤗 Connect To Hugging Face

Use Hugging Face Inference Router with the built-in LLM agent integration:

```bash
export LLM_PROVIDER=hf
export HF_TOKEN=hf_xxxxxxxxxxxxx
export HF_API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
```

Run inference:

```bash
python inference.py --agent llm --episodes 3
```

`LLM_PROVIDER=auto` also works and now auto-selects Hugging Face when only `HF_TOKEN` is configured.

---

## 🚀 Deploy To Hugging Face Space

Full deployment guide:

- See `DEPLOY_TO_HUGGINGFACE.md`

Quick deploy from PowerShell:

```powershell
./scripts/deploy_to_hf.ps1 -SpaceId "your-username/feature-flag-agent-env"
```
