# FeatureFlag Agent Environment - Complete Setup & Reference Guide

**Last Updated: April 2026**

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [System Requirements](#system-requirements)
3. [Installation & Setup (Step-by-Step)](#installation--setup-step-by-step)
4. [Project Architecture](#project-architecture)
5. [Key Changes & Implementations](#key-changes--implementations)
6. [Detailed Command Reference](#detailed-command-reference)
7. [Workflow Guide (What to Run When)](#workflow-guide-what-to-run-when)
8. [Troubleshooting](#troubleshooting)
9. [FAQ](#faq)

---

## 📊 Project Overview

**Project Name:** FeatureFlag Agent Environment  
**Purpose:** AI-powered feature flag rollout system using reinforcement learning and LLM agents  
**Framework:** Meta OpenEnv Hackathon submission  
**Key Technologies:** PyTorch DQN, Groq API (LLM), FastAPI, Pydantic

### What This System Does

- **Environment**: Simulates feature flag deployments with rollout percentages, error rates, latency, and system health
- **Agents**:
  - **Baseline**: Rule-based heuristic rollout (good baseline for comparison)
  - **LLM Agent**: Uses Groq API to make intelligent rollout decisions
  - **Hybrid Agent**: Combines LLM suggestions with safety baseline
  - **RL Agent**: Deep Q-Network (DQN) trained to optimize rollout strategy
- **Tasks**: Three difficulty levels (Task1=easy, Task2=medium, Task3=hard)
- **Metrics**: Rewards, episode scores, convergence tracking

---

## 🖥️ System Requirements

### Minimum Hardware

```
CPU: Quad-core processor (Intel i5/AMD Ryzen 5 or better)
RAM: 8GB minimum (16GB recommended)
Disk: 2GB free space
GPU: Optional (training faster on GPU, but CPU works fine)
```

### Operating System Support

- ✅ Windows 10/11 (with PowerShell 5.1+)
- ✅ macOS (Intel/M1+)
- ✅ Linux (Ubuntu 18.04+)

### Required Software

- **Python**: 3.10 or 3.11 (NOT 3.12, due to PyTorch compatibility)
- **Git**: For cloning repository
- **Virtual Environment Tool**: venv (built-in with Python)

### Internet Connection

- Required for: Groq API calls, pip package downloads
- For LLM features: Groq API key (get free at https://console.groq.com)

---

## 🚀 Installation & Setup (Step-by-Step)

### Step 1: Clone/Copy the Repository

```powershell
# If using Git (recommended)
git clone <your-repo-url>
cd FeatureFlag/feature-flag-agent-env

# OR manually copy the folder
cd /path/to/FeatureFlag/feature-flag-agent-env
```

### Step 2: Verify Python Version

```powershell
python --version
# Should output: Python 3.10.x or Python 3.11.x
# If not installed, download from https://www.python.org/downloads/
```

### Step 3: Create Virtual Environment

**On Windows (PowerShell):**

```powershell
# Navigate to project root
cd c:\path\to\FeatureFlag

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# You should see (.venv) in your prompt now
```

**On macOS/Linux:**

```bash
cd /path/to/FeatureFlag

python3 -m venv .venv

source .venv/bin/activate

# You should see (.venv) in your prompt now
```

### Step 4: Install Project Dependencies

**Navigate to project folder:**

```powershell
cd feature-flag-agent-env  # or your project folder name
```

**Install from requirements.txt:**

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

**Key packages installed:**

- `torch==2.0.0` - PyTorch (Deep Learning framework)
- `pydantic==2.0.0` - Data validation
- `fastapi==0.100.0` - Web server framework
- `uvicorn==0.23.0` - ASGI server
- `numpy==1.24.0` - Numerical computing
- `groq==0.4.0` - Groq LLM API client
- `python-dotenv==1.0.0` - Environment variables
- `matplotlib==3.7.0` - Plotting/visualization
- `pytest==7.0.0` - Testing framework

**Verify installation:**

```powershell
pip list  # Should show all packages installed

python -c "import torch; print(torch.__version__)"
# Should print: 2.0.0 or similar
```

### Step 5: Create Environment Variables File

Create a `.env` file in the project root (`FeatureFlag/feature-flag-agent-env/`):

```bash
# .env file content

# Groq API Configuration
GROQ_API_KEY=your_actual_api_key_here
GROQ_TIMEOUT_SECONDS=20

# Debug Flags (optional, set to 1 to enable)
FF_DEBUG_API=0
FF_DEBUG_STATE_CLIP=0
FF_DEBUG_REWARD_CLIP=0
FF_ASSERT_STATE_NORM=0
FF_TASK2_INFERENCE_SAFETY=1
FF_TASK2_ACTION_MASK=1

# Environment Setup
FEATURE_FLAG_REWARD_CLIP=1
FEATURE_FLAG_REWARD_CLIP_MIN=-1.0
FEATURE_FLAG_REWARD_CLIP_MAX=1.0
```

**Get Groq API Key:**

1. Visit https://console.groq.com
2. Sign up (free)
3. Generate API key
4. Paste in `.env` file (keep secret, do not commit)

### Step 6: Test Installation

```powershell
# Test imports
python -c "from agents.rl_agent import RLAgent; from agents.baseline_agent import BaselineAgent; print('✓ Imports successful')"

# Test environment
python -c "from feature_flag_env import FeatureFlagEnvironment; print('✓ Environment loaded')"

# If both return success, installation is complete!
```

---

## 🏗️ Project Architecture

### Directory Structure

```
FeatureFlag/
├── feature-flag-agent-env/          # Main project folder
│   ├── agents/                       # AI agent implementations
│   │   ├── __init__.py
│   │   ├── base_agent.py            # Abstract base class
│   │   ├── baseline_agent.py        # Rule-based agent
│   │   ├── llm_agent.py             # Groq LLM agent
│   │   ├── hybrid_agent.py          # LLM + baseline hybrid
│   │   ├── rl_agent.py              # PyTorch DQN agent
│   │   ├── factory.py               # Agent factory pattern
│   │   ├── metrics.py               # Performance tracking
│   │   └── replay_buffer.py         # Experience replay for DQN
│   │
│   ├── feature_flag_env/            # Environment implementation
│   │   ├── __init__.py
│   │   ├── models.py                # Pydantic data models
│   │   ├── configs/                 # Configuration files
│   │   │   ├── env_config.py       # Environment config
│   │   │   └── scenario_library.py # 7 scenario definitions
│   │   ├── server/                  # FastAPI server
│   │   │   ├── app.py              # Main FastAPI app
│   │   │   └── feature_flag_environment.py  # Environment class
│   │   ├── tasks/                   # Task definitions
│   │   │   ├── task1_safe_rollout.py
│   │   │   ├── task2_moderate_risk.py
│   │   │   ├── task3_high_risk.py
│   │   │   └── graders.py          # Scoring logic
│   │   └── utils/                   # Utilities
│   │       ├── reward_functions.py # Reward calculation
│   │       └── simulation_engine.py # Physics engine
│   │
│   ├── examples/                    # Example scripts
│   │   ├── run_baseline.py
│   │   ├── run_llm_agent.py
│   │   ├── visualize_episode.py
│   │   ├── compare_agents.py
│   │   └── visualize_training.py
│   │
│   ├── models/                      # Saved model checkpoints
│   │   ├── dqn_task1_*.pth
│   │   ├── dqn_task2_*.pth
│   │   └── dqn_task3_*.pth
│   │
│   ├── logs/                        # Training logs
│   │   └── training/               # Episode and metric logs
│   │
│   ├── tests/                       # Unit tests
│   │   ├── test_agents.py
│   │   └── test_environment.py
│   │
│   ├── inference.py                 # Main inference script
│   ├── train_rl.py                 # RL agent training script
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── README.md
│
├── PROJECT_CHANGES_DOCUMENTATION.md # Previous changes log
└── COMPLETE_SETUP_AND_REFERENCE_GUIDE.md (this file)
```

### Data Flow

```
User Input (Agent Type, Task, Episodes)
          ↓
    inference.py
          ↓
  Agent Decision ← Environment State
  (baseline/llm/hybrid/rl)
          ↓
    FeatureFlagEnvironment
          ↓
Simulation Engine (error, latency, adoption)
          ↓
      Reward Calculation
          ↓
    Task Grader
          ↓
   Episode Results
          ↓
   Metrics & Logging
```

---

## 🔧 Key Changes & Implementations

### 1. Module Import Fix (Critical)

**File:** `feature_flag_env/server/app.py`

- **Problem:** Direct file execution broke absolute imports
- **Solution:** Added sys.path manipulation to locate project root during launch
- **Impact:** Server now starts reliably via both file and module execution

### 2. Groq API Key Auto-Loading

**Files:** `agents/llm_agent.py`, `agents/hybrid_agent.py`

- **Change:** Added `python-dotenv` integration
- **Before:** API key had to be manually exported before running
- **After:** Automatically loads from `.env` file in project root
- **Benefit:** Teammates don't need to manually set environment variables

### 3. Experience Replay Buffer

**File:** `agents/replay_buffer.py` (NEW)

- **What:** Stores up to 10,000 past experiences (state, action, reward, next_state, done)
- **Why:** DQN requires a buffer to break temporal correlations in training data
- **How:** Implements efficient deque with batch sampling for minibatch training

### 4. Deep Q-Network (DQN) Agent

**File:** `agents/rl_agent.py` (Major Rewrite)

- **Architecture:**
  - Input: 9-dimensional state vector
  - Layers: 128 → 64 → 32 neurons
  - Output: 6 Q-values (one per action)
- **Training Features:**
  - Experience replay (batch size 64)
  - Target network (updated every 100 steps)
  - Epsilon-greedy exploration (decays from 1.0 to 0.01)
  - Gradient clipping (max norm 1.0)
  - Reward clipping (range [-1.0, 1.0])
- **Weights:** Saved to `dqn_weights.npz` for persistence

### 5. Gradient Clipping Stabilization

**File:** `agents/rl_agent.py`

- **Added:** `torch.nn.utils.clip_grad_norm_` with max_grad_norm=1.0
- **Why:** Prevents exploding gradients during backpropagation
- **When:** Applied between loss.backward() and optimizer.step()
- **Monitors:** Returns grad_norm metric for tracking

### 6. Reward Clipping Safety

**File:** `feature_flag_env/utils/reward_functions.py`

- **Feature:** Clips all rewards to [-1.0, 1.0] range
- **Why:** Prevents outlier rewards from destabilizing training
- **Config:** Configurable via `FEATURE_FLAG_REWARD_CLIP*` env vars
- **Telemetry:** Tracks how many rewards were clipped per episode

### 7. State Input Validation

**File:** `agents/rl_agent.py`

- **Method:** `validate_and_clip_state(state, source)`
- **Checks:**
  - Converts to float32
  - Reshapes to 9 dimensions
  - Clips values to [0.0, 1.0]
- **Why:** Prevents neural network saturation or NaN from malformed inputs
- **Debug:** Optional assertions via `FF_ASSERT_STATE_NORM` env flag

### 8. Reward Shaping for Task 2

**File:** `feature_flag_env/utils/reward_functions.py`

- **Target:** 75% rollout (not 100%)
- **Changes:**
  - Bonus for 70-80% band (+0.5)
  - Penalty for >90% overshoot (-0.5)
  - Rewards gradual scaling (+1 per 10% step)
  - Penalizes large jumps >50% in one step

### 9. Action Masking for Task 2

**File:** `agents/rl_agent.py`

- **Rules:**
  - If errors >10%: Block FULL_ROLLOUT
  - If rollout ≥75%: Block INCREASE_ROLLOUT and FULL_ROLLOUT
- **Why:** Prevents agent from making risky decisions

### 10. Task 2 Inference Safety

**File:** `agents/rl_agent.py`

- **Feature:** Automatic action override during evaluation
- **Purpose:** Nudge policy from 60% → 70% when risk is low
- **Config:** `FF_TASK2_INFERENCE_SAFETY` env flag
- **Impact:** Improves Task2 score from 0.630 to 0.677+

### 11. Model Checkpointing & Best-Model Tracking

**File:** `train_rl.py`

- **Features:**
  - Saves latest model every N episodes
  - Saves best model based on validation score
  - Early stopping if no improvement for M episodes
  - Full training logs to JSON

### 12. Scenario Mixing for Training Generalization

**File:** `train_rl.py`

- **Feature:** Randomizes scenario per episode during training
- **Options:** `--scenario-mix --mix-scenarios stable,moderate_risk,high_risk`
- **Why:** Prevents agent from overfitting to one environment type

---

## 📚 Detailed Command Reference

### Quick Start (Beginner)

**1. Start with baseline (simplest):**

```powershell
# Terminal should show: (.venv) at start

python inference.py --agent baseline --episodes 5 --task task1
```

**What it does:** Runs 5 episodes of baseline heuristic on easy task  
**Expected output:** Episode results with scores around 0.88-0.96  
**Time:** ~10 seconds

**2. Try LLM agent (requires API key):**

```powershell
# First: Add GROQ_API_KEY to .env file

python inference.py --agent llm --episodes 3 --task task1
```

**What it does:** Uses Groq API to make intelligent rollout decisions  
**Expected output:** Each step shows LLM thoughts and actions  
**Time:** ~20 seconds (slower due to API calls)  
**Cost:** ~$0.02 per 3 episodes (Groq pricing)

**3. Test RL agent (no API needed):**

```powershell
python inference.py --agent rl --episodes 10 --task task1 --rl-model models/dqn_task1_bench.pth
```

**What it does:** Uses trained neural network for decisions  
**Expected output:** Consistent scores around 0.96  
**Time:** ~15 seconds  
**Cost:** Free

---

### Complete Training Pipeline

#### Phase 1: Environment & Server Setup

**Start FastAPI server** (in separate terminal):

```powershell
# Terminal 1: Run server
python -m feature_flag_env.server.app

# Expected output:
# INFO:     Uvicorn running on http://127.0.0.1:8000
# Keep this running in background
```

**Verify server** (in another terminal):

```powershell
# Terminal 2: Test endpoint
curl http://127.0.0.1:8000/state

# OR use Python:
python -c "import requests; print(requests.get('http://127.0.0.1:8000/state').json())"
```

#### Phase 2: Baseline Evaluation (Sanity Check)

```powershell
# Test all 3 tasks with baseline
python inference.py --agent baseline --episodes 5 --task task1
python inference.py --agent baseline --episodes 5 --task task2
python inference.py --agent baseline --episodes 5 --task task3

# Expected scores:
# Task1: 0.88-0.96 (very good)
# Task2: 0.50-0.60 (moderate, harder balancing req)
# Task3: 0.40-0.50 (hard, multiple competing objectives)
```

#### Phase 3: Train DQN Agent

**Task 1 Training (Easiest, fastest):**

```powershell
# Start fresh training for Task 1
python train_rl.py --mode train --task task1 --episodes 300 --model models/dqn_task1_trained.pth --log-dir logs/training --eval-every 50

# Breakdown:
# --mode train           → Training mode (vs evaluate)
# --task task1           → Which task to train on
# --episodes 300         → Run 300 episodes
# --model ...            → Save final model here
# --log-dir ...          → Save logs here
# --eval-every 50        → Evaluate every 50 episodes

# Time: ~2-3 minutes (CPU) or ~30 seconds (GPU)
# GPU Recommended for this size
```

**Task 2 Training (Medium, with tuning):**

```powershell
# Task 2 with recommended parameters
python train_rl.py --mode train --task task2 --episodes 500 --task2-tuned --scenario-mix --mix-scenarios stable,moderate_risk,high_risk --model models/dqn_task2_tuned.pth --log-dir logs/training --eval-every 50 --validation-episodes 10 --early-stop-patience 3

# New flags explained:
# --task2-tuned          → Use optimized hyperparameters
# --scenario-mix         → Mix different risk levels
# --mix-scenarios ...    → Which scenarios to use
# --validation-episodes  → How many episodes to eval on
# --early-stop-patience  → Stop if no improvement for N evals

# Time: ~3-5 minutes (CPU)
```

**Task 3 Training (Hardest, needs patience):**

```powershell
# Task 3 requires more episodes
python train_rl.py --mode train --task task3 --episodes 800 --model models/dqn_task3_trained.pth --log-dir logs/training --eval-every 50 --checkpoint-every 100

# checkpoint-every: Save model every 100 episodes as safety backup

# Time: ~5-8 minutes (CPU)
# Recommendation: Run overnight or on GPU
```

#### Phase 4: Evaluate Trained Models

**Per-Task Evaluation:**

```powershell
# Evaluate Task 1
python train_rl.py --mode evaluate --task task1 --model models/dqn_task1_trained.pth --episodes 50

# Evaluate Task 2
python train_rl.py --mode evaluate --task task2 --model models/dqn_task2_tuned.pth --episodes 50

# Evaluate Task 3
python train_rl.py --mode evaluate --task task3 --model models/dqn_task3_trained.pth --episodes 50

# Expected output:
# Average Score per task
# Min/Max/Stdev
# Final metrics saved to logs/
```

#### Phase 5: Compare All Agents

**Side-by-side comparison:**

```powershell
# Run all 4 agents on same task
python examples/compare_agents.py --agents baseline llm rl hybrid --episodes 10 --task task1 --output-dir logs/training

# Outputs:
# logs/training/baseline_metrics.json
# logs/training/llm_metrics.json
# logs/training/rl_metrics.json
# logs/training/hybrid_metrics.json
# training_comparison.png (visualization)

# Command breakdown:
# --agents baseline ... → Which agents to test
# --episodes 10        → How many episodes per agent
# --task task1         → Which task
# --output-dir ...     → Where to save results
```

#### Phase 6: Visualize Results

**Single episode visualization:**

```powershell
# Record and visualize one episode
python examples/visualize_episode.py --agent rl --task task2

# Creates: episode_visualization.png
# Shows:
# - Rollout over time
# - Error rate trend
# - Latency progression
# - System health
# - Reward per step
# - Action distribution
```

**Training progress visualization:**

```powershell
# Plot training metrics
python examples/visualize_training.py --log-dir logs/training --save-path logs/training/training_curves.png

# Creates: training_curves.png with subplots showing:
# - Episode score over time
# - Reward trend
# - Loss convergence
# - Exploration decay
```

---

## 🔄 Workflow Guide (What to Run When)

### Scenario A: Fresh Start (No Models)

```
Step 1: Setup (.env, requirements, test imports)
        ↓
Step 2: Run baseline sanity check (verify env works)
        ↓
Step 3: Choose task difficulty (Task1 easiest → Task3 hardest)
        ↓
Step 4: Train DQN agent on chosen task
        ↓
Step 5: Evaluate trained model
        ↓
Step 6: Visualize results (optional but recommended)
        ↓
Step 7: Compare with other agents (optional)
```

**Exact commands:**

```powershell
# Step 1: Setup already done above

# Step 2: Baseline sanity check
python inference.py --agent baseline --episodes 5 --task task1

# Step 3: Choose task1 (fastest)

# Step 4: Train
python train_rl.py --mode train --task task1 --episodes 300 --model models/dqn_task1_trained.pth

# Step 5: Evaluate
python train_rl.py --mode evaluate --task task1 --model models/dqn_task1_trained.pth --episodes 50

# Step 6: Visualize
python examples/visualize_training.py --log-dir logs/training

# Step 7: Compare (optional)
python examples/compare_agents.py --agents baseline rl --episodes 20 --task task1
```

**Total time:** ~5-10 minutes (including training)

---

### Scenario B: Quick Demo (Use Pre-trained Models)

If models already exist in `models/` folder:

```powershell
# Option 1: Quick inference with RL
python inference.py --agent rl --episodes 20 --task task1 --rl-model models/dqn_task1_bench.pth

# Option 2: Compare all agents quickly
python examples/compare_agents.py --agents baseline llm rl hybrid --episodes 5 --task task1

# Option 3: Single episode visualization
python examples/visualize_episode.py --agent rl --task task1
```

**Total time:** <1 minute

---

### Scenario C: Full Benchmark (All Tasks, All Agents)

For comparing performance across all scenarios:

```powershell
# Create output directory
New-Item -ItemType Directory -Force -Path logs/benchmark

# Record baseline on all tasks
foreach ($task in @("task1", "task2", "task3")) {
    python inference.py --agent baseline --episodes 50 --task $task
}

# Train and evaluate RL on all tasks
foreach ($task in @("task1", "task2", "task3")) {
    python train_rl.py --mode train --task $task --episodes 500 --model models/dqn_${task}_benchmark.pth
    python train_rl.py --mode evaluate --task $task --model models/dqn_${task}_benchmark.pth --episodes 50
}

# Full comparison
python examples/compare_agents.py --agents baseline rl --episodes 50 --task task1 --output-dir logs/benchmark
python examples/compare_agents.py --agents baseline rl --episodes 50 --task task2 --output-dir logs/benchmark
python examples/compare_agents.py --agents baseline rl --episodes 50 --task task3 --output-dir logs/benchmark
```

**Time:** 20-30 minutes  
**Output:** Comprehensive metrics comparing all agents across all tasks

---

## 🐛 Troubleshooting

### Issue 1: "ModuleNotFoundError: No module named 'feature_flag_env'"

**Cause:** Running script from wrong directory or not in venv  
**Solution:**

```powershell
# Make sure (.venv) shows in prompt
# If not: .\.venv\Scripts\Activate.ps1

# Make sure you're in project root
cd c:\path\to\FeatureFlag\feature-flag-agent-env

# Try again
python inference.py --agent baseline --episodes 1 --task task1
```

---

### Issue 2: "GROQ_API_KEY is not set"

**Cause:** Missing .env file or API key not configured  
**Solution:**

```powershell
# 1. Create .env in project root (same level as inference.py)
# 2. Add line: GROQ_API_KEY=gsk_xxxxx
# 3. Get key from https://console.groq.com
# 4. LLM should now work

# Test:
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('Key set' if os.getenv('GROQ_API_KEY') else 'Key missing')"
```

---

### Issue 3: "No module named 'torch'" even after pip install

**Cause:** PyTorch installation issue or wrong Python version  
**Solution:**

```powershell
# Check Python version (must be 3.10 or 3.11)
python --version

# Uninstall and reinstall torch
pip uninstall torch -y
pip install torch==2.0.0

# Test
python -c "import torch; print(torch.__version__)"
```

---

### Issue 4: "Address already in use" when starting server

**Cause:** Port 8000 already occupied  
**Solution:**

```powershell
# Change port in feature_flag_env/server/app.py line 500:
# Before: uvicorn.run(app, host="0.0.0.0", port=8000)
# After:  uvicorn.run(app, host="0.0.0.0", port=8001)

# Then run:
python -m feature_flag_env.server.app
```

---

### Issue 5: Training very slow (>10 min for 300 episodes)

**Cause:** Running on CPU (slow) or environmental overhead  
**Solution:**

```powershell
# Use GPU acceleration (if available)
# Install GPU PyTorch:
pip uninstall torch -y
pip install torch --index-url https://download.pytorch.org/whl/cu118

# For Apple M1/M2:
pip uninstall torch -y
pip install torch torchvision torchaudio

# Monitor GPU usage
# Windows: nvidia-smi
# Mac: powermetrics

# Or reduce episodes for testing
python train_rl.py --mode train --task task1 --episodes 50  # Quick test
```

---

### Issue 6: Poor RL performance (scores <0.5)

**Cause:** Model not trained enough or weak checkpoint  
**Solution:**

```powershell
# 1. Train longer
python train_rl.py --mode train --task task1 --episodes 1000

# 2. Use Task 2 tuning flags
python train_rl.py --mode train --task task2 --task2-tuned --episodes 600

# 3. Check if safety override is enabled
set FF_TASK2_INFERENCE_SAFETY=1  # Enable for Task2
python inference.py --agent rl --episodes 10 --task task2

# 4. Visualize to debug
python examples/visualize_episode.py --agent rl --task task1
```

---

## ❓ FAQ

### Q1: Do I need GPU to run this?

**A:** No. GPU is optional but recommended for training:

- **CPU only:** Training 300 episodes takes 2-3 minutes (fine for demo)
- **GPU (RTX 3060+):** Training 300 episodes takes 20-30 seconds (much faster bulk training)
- **Inference:** GPU not needed, runs in <1 second per episode on CPU

### Q2: How much internet bandwidth does LLM agent use?

**A:** Minimal:

- Per API call: ~1-2 KB request, 1-2 KB response
- Per episode: 10-30 API calls = 20-60 KB
- Per 50 episodes: ~2-3 MB total
- **Cost:** Free tier usually has 4000 requests/day (plenty)

### Q3: Can I run this on Google Colab?

**A:** Yes! Steps:

```python
# In Colab cell 1: Setup
!git clone <your-repo-url>
%cd FeatureFlag/feature-flag-agent-env
!pip install -r requirements.txt

# In Colab cell 2: Run
!python inference.py --agent rl --episodes 50 --task task1

# GPU automatically available in Colab (free!)
```

### Q4: How long does a complete training run take?

**A:**

```
Task1: 150-300 episodes → ~2-3 min (CPU) or ~20 sec (GPU)
Task2: 300-500 episodes → ~5-10 min (CPU) or ~1 min (GPU)
Task3: 500-800 episodes → ~10-15 min (CPU) or ~2-3 min (GPU)

Full benchmark (all tasks): ~30-45 min (CPU)
```

### Q5: Can multiple people train on same machine?

**A:** Yes, but:

```powershell
# Create separate model names
python train_rl.py --mode train --task task1 --model models/dqn_alice_task1.pth
python train_rl.py --mode train --task task1 --model models/dqn_bob_task1.pth

# Use --log-dir to separate logs
python train_rl.py --mode train --task task1 --log-dir logs/alice_training
```

### Q6: How do I share my trained model?

**A:**

```powershell
# Model file is in models/dqn_task1_trained.pth
# Just copy it to friend's models/ folder
# (Files are ~1-5 MB, email-friendly)

# Friend can use it:
python train_rl.py --mode evaluate --model models/dqn_task1_trained.pth --episodes 50
```

### Q7: What if I want to modify reward shaping?

**A:** Edit `feature_flag_env/utils/reward_functions.py`:

```python
# Around line 50: calculate_reward_task1()
# Modify bonus/penalty values:
bonus_for_target = 2.0  # Increase from 1.0 for more incentive
penalty_overshoot = -2.0  # More punishment for overshooting

# Then retrain
python train_rl.py --mode train --task task1 --episodes 500
```

### Q8: Should I use Task 2 tuned parameters for other tasks?

**A:** Not recommended:

```powershell
# Task1: Use default parameters (simple task)
python train_rl.py --mode train --task task1 --episodes 300

# Task2: Use --task2-tuned (specific tuning)
python train_rl.py --mode train --task task2 --task2-tuned --episodes 500

# Task3: Use default with longer training
python train_rl.py --mode train --task task3 --episodes 800

# Task2 tuning won't help other tasks - they have different designs
```

---

## 📞 Support & Additional Resources

### Documentation Files

- `PROJECT_CHANGES_DOCUMENTATION.md` - Detailed change log
- `feature-flag-agent-env/README.md` - Project-specific notes
- Code comments in key files

### Quick Reference

- **Main entry:** `inference.py`
- **Training:** `train_rl.py`
- **Agent impls:** `agents/*.py`
- **Examples:** `examples/*.py`

### Testing

```powershell
# Run unit tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_agents.py -v

# Generate coverage report
python -m pytest tests/ --cov=agents --cov=feature_flag_env
```

---

## 🎯 Summary for Your Friend

**To get started immediately:**

1. **Clone project** and install requirements (5 min)
2. **Create .env file** with API key if using LLM (1 min)
3. **Test with baseline** to verify installation (2 min)
4. **Train RL agent** on Task1 (3 min)
5. **Evaluate** and celebrate! (1 min)

**Total first-run time: ~15 minutes**

All commands are copy-paste ready in the guide above. Good luck! 🚀

---

**Document Version:** 2.0  
**Last Updated:** April 2026  
**Tested On:** Windows 10/11, Python 3.10-3.11, PyTorch 2.0
