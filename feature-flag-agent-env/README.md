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

Set these variables before running the LLM or hybrid agents:

```bash
# Force Hugging Face provider
export LLM_PROVIDER=hf

# Hugging Face token and endpoint
export HF_TOKEN=hf_xxxxxxxxxxxxx
export HF_API_BASE_URL=https://router.huggingface.co/v1

# Choose a Hugging Face model
export MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
```

Then run:

```bash
python inference.py --agent llm --episodes 3
python inference.py --agent hybrid --episodes 3
```

If `LLM_PROVIDER=auto`, the agent now auto-selects Hugging Face when only `HF_TOKEN` is present.

---

## 📈 Training Evidence (Task1)

To include training progress in submission artifacts:

```bash
# Generate Task1 convergence figure from training logs
python examples/visualize_training.py --log-dir logs/training --save-path logs/training/task1_convergence.png
```

The latest Task1 run shows clear convergence in reward and episode efficiency:
- Early training avg reward (first 10 episodes): `1.931`
- Late training avg reward (last 100 episodes): `2.130`
- Best episode reward: `2.140`

![Task1 training convergence](logs/training/task1_convergence.png)

This demonstrates learning progression using logged training data without changing rollout behavior for submission evaluation.
