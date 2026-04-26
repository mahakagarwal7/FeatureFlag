# Deploy To Hugging Face Spaces (Docker)

This repository supports deployment from repository root.

## Prerequisites

- Hugging Face account
- Write token for Spaces
- Git installed
- Docker Space already created

## Create a Space

1. Open https://huggingface.co/new-space
2. Choose:
- Owner: your account/org
- Space name: for example feature-flag-ai
- SDK: Docker

Space ID format:

- username/space-name

## Configure Secrets and Variables

In Space Settings -> Variables and secrets:

Variables:

- LLM_PROVIDER = hf
- MODEL_NAME = Qwen/Qwen2.5-7B-Instruct
- HF_API_BASE_URL = https://router.huggingface.co/v1

Secrets:

- HF_TOKEN = hf_xxx

Optional:

- HF_CHAT_COMPLETIONS_URL = https://router.huggingface.co/v1/chat/completions

## Deploy (PowerShell)

From repository root:

```powershell
./scripts/deploy_to_hf.ps1 -SpaceId "your-username/feature-flag-ai"
```

Or with explicit token:

```powershell
./scripts/deploy_to_hf.ps1 -SpaceId "your-username/feature-flag-ai" -Token "hf_xxx"
```

## Manual Alternative

```powershell
hf auth login --token $env:HF_TOKEN --add-to-git-credential

git remote add hf https://huggingface.co/spaces/your-username/feature-flag-ai
git add .
git commit -m "Deploy to Hugging Face Space"
git push hf HEAD:main
```

## Verify

- Open the Space URL
- Check Space logs
- Check health endpoint at /health
