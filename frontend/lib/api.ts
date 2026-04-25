/**
 * API client for the Feature Flag Agent Environment.
 * Connects the Next.js frontend to the FastAPI backend.
 */

const API_BASE_URL_STORAGE_KEY = "feature_flag_api_base_url";
const API_KEY_STORAGE_KEY = "feature_flag_api_key";

const ENV_BASE_URL = process.env.NEXT_PUBLIC_API_URL?.trim();
const DEFAULT_BASE_URLS = [
  "http://127.0.0.1:8000",
  "http://127.0.0.1:7860",
  "http://localhost:8000",
  "http://localhost:7860",
];

let resolvedBaseUrl: string | null = null;

function normalizeBaseUrl(url: string): string {
  return url.replace(/\/$/, "");
}

function readStoredBaseUrl(): string | null {
  if (typeof window === "undefined") return null;
  const stored = localStorage.getItem(API_BASE_URL_STORAGE_KEY)?.trim();
  return stored ? normalizeBaseUrl(stored) : null;
}

function getCandidateBaseUrls(): string[] {
  const candidates = [
    readStoredBaseUrl(),
    ENV_BASE_URL ? normalizeBaseUrl(ENV_BASE_URL) : null,
    ...DEFAULT_BASE_URLS,
  ].filter((value): value is string => Boolean(value));

  return [...new Set(candidates)];
}

function makeConnectionErrorMessage(): string {
  return "Unable to reach backend API. Verify backend is running and set NEXT_PUBLIC_API_URL (or API Base URL in Settings).";
}

async function parseResponse(res: Response): Promise<unknown> {
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return res.json();
  }
  return res.text();
}

async function resolveBaseUrl(getHeaders: () => HeadersInit): Promise<string> {
  if (resolvedBaseUrl) return resolvedBaseUrl;

  const urls = getCandidateBaseUrls();
  let lastError: unknown = null;

  for (const base of urls) {
    try {
      const res = await fetch(`${base}/health`, {
        method: "GET",
        headers: getHeaders(),
      });

      if (res.ok) {
        resolvedBaseUrl = base;
        return base;
      }
    } catch (error) {
      lastError = error;
    }
  }

  if (lastError) {
    throw new Error(makeConnectionErrorMessage());
  }

  throw new Error(makeConnectionErrorMessage());
}

export interface Observation {
  current_rollout_percentage: number;
  error_rate: number;
  latency_p99_ms: number;
  user_adoption_rate: number;
  revenue_impact: number;
  system_health_score: number;
  active_users: number;
  feature_name: string;
  time_step: number;
}

export interface State {
  episode_id: string;
  step_count: number;
  total_reward: number;
  is_done: boolean;
  scenario_name: string;
  difficulty: string;
  history: Array<{
    observation?: Observation;
    reward?: number;
    [key: string]: unknown;
  }>;
}

export interface StepResponse {
  observation: Observation;
  reward: number;
  done: boolean;
  info: Record<string, unknown>;
}

export interface DashboardData {
  summary: {
    health_score: number;
    error_rate: number;
    latency_p99_ms: number;
    uptime_seconds: number;
    status: string;
  };
  metrics: {
    latency: { current: number; trend: number };
    error_rate: { current: number; trend: number };
    adoption: { current: number; trend: number };
  };
  alerts: Array<Record<string, unknown>>;
}

export const api = {
  getApiBaseUrl(): string | null {
    return readStoredBaseUrl() || (ENV_BASE_URL ? normalizeBaseUrl(ENV_BASE_URL) : null);
  },

  setApiBaseUrl(url: string) {
    if (typeof window !== "undefined") {
      const normalized = normalizeBaseUrl(url.trim());
      localStorage.setItem(API_BASE_URL_STORAGE_KEY, normalized);
      resolvedBaseUrl = normalized;
    }
  },

  getApiKey(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(API_KEY_STORAGE_KEY);
  },

  setApiKey(key: string) {
    if (typeof window !== "undefined") {
      localStorage.setItem(API_KEY_STORAGE_KEY, key);
    }
  },

  getHeaders(): HeadersInit {
    const headers: HeadersInit = {
      "Content-Type": "application/json",
    };
    const key = this.getApiKey();
    if (key) {
      headers["X-API-Key"] = key;
    }
    return headers;
  },

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const base = await resolveBaseUrl(() => this.getHeaders());

    let res: Response;
    try {
      res = await fetch(`${base}${path}`, {
        ...init,
        headers: {
          ...this.getHeaders(),
          ...(init.headers || {}),
        },
      });
    } catch {
      throw new Error(makeConnectionErrorMessage());
    }

    if (!res.ok) {
      let message = `Request failed (${res.status})`;
      try {
        const payload = await parseResponse(res);
        if (typeof payload === "string") {
          message = payload;
        } else if (payload && typeof payload === "object" && "detail" in payload) {
          const detail = (payload as { detail?: unknown }).detail;
          if (typeof detail === "string") {
            message = detail;
          }
        }
      } catch {
        // Keep fallback message
      }
      throw new Error(message);
    }

    return (await parseResponse(res)) as T;
  },

  async getHealth(): Promise<{ status?: string; environment_ready?: boolean }> {
    return this.request<{ status?: string; environment_ready?: boolean }>("/health", { method: "GET" });
  },

  async reset(): Promise<unknown> {
    return this.request<unknown>("/reset", {
      method: "POST",
    });
  },

  async step(action: { action_type: string; target_percentage: number; reason: string }): Promise<StepResponse> {
    return this.request<StepResponse>("/step", {
      method: "POST",
      body: JSON.stringify(action),
    });
  },

  async getState(): Promise<State> {
    try {
      return this.request<State>("/state", { method: "GET" });
    } catch (error) {
      // Environment may not be initialized yet; reset once and retry.
      if (error instanceof Error && /not initialized|400/i.test(error.message)) {
        await this.reset();
        return this.request<State>("/state", { method: "GET" });
      }
      throw error;
    }
  },

  async getDashboard(): Promise<DashboardData> {
    try {
      return this.request<DashboardData>("/monitoring/dashboard", { method: "GET" });
    } catch (error) {
      // Monitoring can be disabled on backend; fall back to core state/health data.
      if (error instanceof Error && /(403|monitoring is not enabled)/i.test(error.message)) {
        const [health, state] = await Promise.all([
          this.getHealth(),
          this.getState(),
        ]);

        const last = state.history?.[state.history.length - 1]?.observation;
        const latency = Number(last?.latency_p99_ms ?? 0);
        const err = Number(last?.error_rate ?? 0);
        const adoption = Number(last?.user_adoption_rate ?? 0);

        return {
          summary: {
            health_score: Number(health?.environment_ready ? (last?.system_health_score ?? 1) : 0),
            error_rate: err,
            latency_p99_ms: latency,
            uptime_seconds: 0,
            status: health?.status || "unknown",
          },
          metrics: {
            latency: { current: latency, trend: 0 },
            error_rate: { current: err, trend: 0 },
            adoption: { current: adoption, trend: 0 },
          },
          alerts: [],
        };
      }
      throw error;
    }
  },
};
