# Frontend Setup (FeatureFlag)

This frontend connects to the FastAPI backend used by the feature rollout simulation.

## 1) Configure Environment

Create `frontend/.env.local` from `frontend/.env.example`:

```bash
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

If your backend runs on another port (for example 7860), set it accordingly.

## 2) Start Backend

From repository root:

```bash
python -m feature_flag_env.server.app
```

Default health endpoint:

- `http://127.0.0.1:8000/health`

## 3) Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

- `http://localhost:3000`

## 4) Configure API Key and URL in UI

In **Settings** page:

- Save your `X-API-Key` value.
- Save your API base URL if it differs from `.env`.
- Use **Test** to verify backend connectivity.

## Notes

- Backend CORS allowlist is configured through `FRONTEND_ORIGINS` in backend `.env`.
- Frontend API client supports fallback between common local ports (`8000`, `7860`) if no URL is configured.
- If monitoring endpoints are disabled in backend config, dashboard gracefully falls back to core health/state data.
