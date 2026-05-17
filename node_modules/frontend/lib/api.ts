/**
 * API client for the Feature Flag Agent Environment.
 * Connects the Next.js frontend to the FastAPI backend.
 */

const API_BASE_URL_STORAGE_KEY = "feature_flag_api_base_url";
const API_KEY_STORAGE_KEY = "feature_flag_api_key";

let resolvedBaseUrl: string | null = null;

function normalizeBaseUrl(url: string): string {
  return url.replace(/\/$/, "");
}

const normalizeUrl = (base: string, endpoint: string): string => {
  return `${base.replace(/\/+$/, '')}/${endpoint.replace(/^\/+/, '')}`;
};

function readStoredBaseUrl(): string | null {
  if (typeof window === "undefined") return null;
  const stored = localStorage.getItem(API_BASE_URL_STORAGE_KEY)?.trim();
  return stored ? normalizeBaseUrl(stored) : null;
}

/**
 * Resolve API base URL with environment awareness.
 * Priority: 1) Runtime env var, 2) Build-time env var, 3) Fallback defaults
 */
export const getApiBaseUrl = (): string => {
  // Client-side: Use NEXT_PUBLIC_ prefixed vars (exposed to browser)
  if (typeof window !== 'undefined') {
    return (
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      (process.env.NEXT_PUBLIC_VERCEL_URL ? `https://${process.env.NEXT_PUBLIC_VERCEL_URL}/api` : undefined) ||
      'http://localhost:8000' // Local dev fallback
    );
  }
  
  // Server-side (Node.js): Use non-prefixed vars
  return (
    process.env.API_BASE_URL ||
    (process.env.ENV_HOST && process.env.ENV_PORT ? `http://${process.env.ENV_HOST}:${process.env.ENV_PORT}` : undefined) ||
    'http://localhost:8000'
  );
};

/**
 * Create a fetch wrapper with automatic base URL and error handling
 */
export const apiFetch = async (
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> => {
  const baseUrl = getApiBaseUrl();
  const url = normalizeUrl(baseUrl, endpoint);
  
  const config: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };
  
  try {
    const response = await fetch(url, config);
    
    // Log errors in development
    if (process.env.NODE_ENV === 'development' && !response.ok) {
      console.error(`API Error: ${response.status} ${response.statusText} at ${url}`);
    }
    
    return response;
  } catch (error) {
    console.error(`Network error fetching ${url}:`, error);
    throw new Error(`Failed to connect to API at ${baseUrl}. Is the backend running?`);
  }
};

function makeConnectionErrorMessage(baseUrl: string): string {
  return `Failed to connect to API at ${baseUrl}. Is the backend running?`;
}

async function parseResponse(res: Response): Promise<unknown> {
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return res.json();
  }
  return res.text();
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

  // Extended: Stakeholders
  stakeholder_devops_sentiment?: number;
  stakeholder_product_sentiment?: number;
  stakeholder_customer_sentiment?: number;
  stakeholder_overall_approval?: boolean;
  stakeholder_feedback_dict?: Record<string, unknown>;
  stakeholder_belief_dict?: Record<string, unknown>;

  // Extended: Missions
  mission_name?: string;
  current_phase?: string;
  phase_index?: number;
  phase_progress?: number;
  phases_completed?: number;
  total_phases?: number;
  phase_objectives?: string[];
  phase_allowed_actions?: string[];

  // Extended: Tools
  tools_connected?: number;
  tools_alerts_active?: number;
  last_tool_result?: Record<string, unknown>;
  tool_memory_summary?: Record<string, unknown>;

  // Extended: Chaos & HITL
  chaos_incident?: Record<string, unknown>;
  approval_status?: string;
  extra_context: Record<string, unknown>;
}

export interface ActionHistoryItem {
  action_type: string;
  target_percentage: number;
  reason: string;
  timestamp: string;
  tool_call?: Record<string, unknown> | null;
}

export interface State {
  episode_id: string;
  step_count: number;
  total_reward: number;
  done?: boolean;
  is_done: boolean;
  scenario_name: string;
  difficulty: string;
  action_history?: ActionHistoryItem[];
  rollout_history?: number[];
  history: Array<{
    observation?: Observation;
    reward?: number;
    action?: Record<string, unknown> | null;
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

export interface MonitoringHealth {
  status: string;
  uptime_seconds: number;
  timestamp: string;
  alerts_enabled: boolean;
  prometheus_enabled: boolean;
  metrics_collection_interval: number;
  alert_check_interval: number;
  current_metrics: {
    error_rate: number;
    latency_p99_ms: number;
    system_health_score: number;
    user_adoption_rate: number;
  };
  thresholds: {
    error_rate_threshold: number;
    latency_threshold_ms: number;
    health_score_threshold: number;
  };
}

export interface MonitoringAlert {
  type?: string;
  severity?: string;
  message?: string;
  details?: Record<string, unknown>;
  [key: string]: unknown;
}

function normalizeDashboard(raw: any): DashboardData {
  const data = (raw && typeof raw === "object") ? raw : {};
  const summary = data.summary || {};
  const metrics = data.metrics || {};
  
  return {
    summary: {
      health_score: Number(summary.health_score ?? 0),
      error_rate: Number(summary.error_rate ?? 0),
      latency_p99_ms: Number(summary.latency_p99_ms ?? 0),
      uptime_seconds: Number(summary.uptime_seconds ?? 0),
      status: String(summary.status ?? "unknown"),
    },
    metrics: {
      latency: {
        current: Number(metrics.latency?.current ?? 0),
        trend: Number(metrics.latency?.trend ?? 0),
      },
      error_rate: {
        current: Number(metrics.error_rate?.current ?? 0),
        trend: Number(metrics.error_rate?.trend ?? 0),
      },
      adoption: {
        current: Number(metrics.adoption?.current ?? 0),
        trend: Number(metrics.adoption?.trend ?? 0),
      },
    },
    alerts: Array.isArray(data.alerts) ? data.alerts : [],
  };
}

export const api = {
  getApiBaseUrl(): string {
    return getApiBaseUrl();
  },

  get: (endpoint: string, options?: RequestInit) => 
    apiFetch(endpoint, { ...options, method: 'GET' }),
  
  post: (endpoint: string, body: any, options?: RequestInit) => 
    apiFetch(endpoint, { 
      ...options, 
      method: 'POST',
      body: JSON.stringify(body),
    }),

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
    const res = await apiFetch(path, {
      ...init,
      headers: {
        ...this.getHeaders(),
        ...(init.headers || {}),
      },
    });

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
      const rawState = await this.request<unknown>("/state", { method: "GET" });
      const stateObj = (rawState && typeof rawState === "object") ? (rawState as Record<string, unknown>) : {};
      
      const historyValue = stateObj["history"];
      const rolloutHistory = stateObj["rollout_history"];
      const actionHistory = stateObj["action_history"];
      const observationHistory = stateObj["observation_history"];

      if (Array.isArray(observationHistory) && observationHistory.length > 0) {
        stateObj["history"] = observationHistory.map((obs: unknown, index: number) => {
          const actionObject = Array.isArray(actionHistory) && index > 0 ? actionHistory[index - 1] : null;
          return {
            observation: obs as Record<string, unknown>,
            action: actionObject && typeof actionObject === "object" ? actionObject : null,
            reward: 0,
          };
        });
      } else if (!Array.isArray(historyValue) && Array.isArray(rolloutHistory)) {
        stateObj["history"] = rolloutHistory.map((obs: unknown, index: number) => {
          const actionTuple =
            Array.isArray(actionHistory) && index > 0 ? (actionHistory[index - 1] as unknown) : null;
          const actionArr = Array.isArray(actionTuple) ? actionTuple : null;
          const action = actionArr && actionArr.length > 0 && actionArr[0] && typeof actionArr[0] === "object"
            ? (actionArr[0] as Record<string, unknown>)
            : null;
          const reward = actionArr && actionArr.length > 1 ? Number(actionArr[1] ?? 0) : 0;
          return {
            observation: obs,
            action,
            reward,
          };
        });
      }
      return stateObj as unknown as State;
    } catch (error) {
      if (error instanceof Error && /not initialized|400/i.test(error.message)) {
        await this.reset();
        return this.getState();
      }
      throw error;
    }
  },

  async getDashboard(): Promise<DashboardData> {
    try {
      const dashboard = await this.request<unknown>("/monitoring/dashboard", { method: "GET" });
      return normalizeDashboard(dashboard);
    } catch (error) {
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

  async getMonitoringHealth(): Promise<MonitoringHealth | null> {
    try {
      return this.request<MonitoringHealth>("/monitoring/health", { method: "GET" });
    } catch (error) {
      if (error instanceof Error && /(403|monitoring is not enabled)/i.test(error.message)) {
        return null;
      }
      throw error;
    }
  },

  async getMonitoringAlerts(): Promise<MonitoringAlert[] | null> {
    try {
      const res = await this.request<unknown>("/monitoring/alerts", { method: "GET" });
      if (Array.isArray(res)) return res as MonitoringAlert[];
      if (res && typeof res === "object" && Array.isArray((res as { alerts?: unknown }).alerts)) {
        return (res as { alerts: MonitoringAlert[] }).alerts;
      }
      return [];
    } catch (error) {
      if (error instanceof Error && /(403|monitoring is not enabled)/i.test(error.message)) {
        return null;
      }
      throw error;
    }
  },

  async getPrometheusMetrics(): Promise<string | null> {
    try {
      return this.request<string>("/metrics", { method: "GET" });
    } catch (error) {
      if (error instanceof Error && /(403|monitoring is not enabled)/i.test(error.message)) {
        return null;
      }
      throw error;
    }
  },
};
