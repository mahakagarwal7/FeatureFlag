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
