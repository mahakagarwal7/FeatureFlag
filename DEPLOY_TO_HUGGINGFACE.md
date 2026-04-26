# Deploy To Hugging Face Spaces (Docker)

This repository is ready for Hugging Face Docker Spaces deployment from the repository root.

## 1. Prerequisites

- A Hugging Face account
- A write token with access to Spaces
- Git installed
- Dockerfile present at repository root

## 2. Create a Space

1. Go to: https://huggingface.co/new-space
2. Choose:
- Owner: your account or org
- Space name: for example, feature-flag-agent-env
- SDK: Docker
- Visibility: Public or Private

The final Space ID format is:
- your-username/feature-flag-agent-env

## 3. Configure Space Secrets and Variables

In Space Settings -> Variables and secrets, add:

- LLM_PROVIDER = hf
- MODEL_NAME = Qwen/Qwen2.5-7B-Instruct
- HF_API_BASE_URL = https://router.huggingface.co/v1

Add as secret:

- HF_TOKEN = hf_xxx

Optional:

- HF_CHAT_COMPLETIONS_URL = https://router.huggingface.co/v1/chat/completions
- API_BASE_URL (only if using OpenAI-compatible endpoint)

## 4. Deploy With Script (Windows PowerShell)

From repository root:

```powershell
./scripts/deploy_to_hf.ps1 -SpaceId "your-username/feature-flag-agent-env"
```

If HF_TOKEN is not set in environment:

```powershell
./scripts/deploy_to_hf.ps1 -SpaceId "your-username/feature-flag-agent-env" -Token "hf_xxx"
```

## 5. Manual Deploy Alternative

```powershell
hf auth login

git remote add hf https://huggingface.co/spaces/your-username/feature-flag-agent-env

git add .
git commit -m "Deploy to Hugging Face Space"
git push hf HEAD:main
```

## 6. Verify Deployment

- Open the Space URL
- Check container logs in Space -> Logs
- Verify health endpoint:
- /health

## 7. Runtime Notes

- Root README already contains Hugging Face frontmatter with sdk: docker and app_port: 7860.
- Root Dockerfile exposes and runs on port 7860 for Spaces compatibility.
- LLM agent supports Hugging Face provider via HF_TOKEN and LLM_PROVIDER=hf.
