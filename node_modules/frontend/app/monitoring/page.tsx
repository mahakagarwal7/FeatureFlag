"use client";

import * as React from "react";
import { api, MonitoringAlert, MonitoringHealth } from "@/lib/api";
import { useEnv } from "@/components/env/env-provider";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

function formatMaybeNumber(value: unknown, digits = 2): string {
  const n = typeof value === "number" ? value : Number(value);
  if (Number.isFinite(n)) return n.toFixed(digits);
  return "—";
}

export default function MonitoringPage() {
  const { connectionState, connectionText } = useEnv();

  const [health, setHealth] = React.useState<MonitoringHealth | null>(null);
  const [alerts, setAlerts] = React.useState<MonitoringAlert[] | null>(null);
  const [metricsText, setMetricsText] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string>("");

  const refresh = React.useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const [h, a, m] = await Promise.all([
        api.getMonitoringHealth(),
        api.getMonitoringAlerts(),
        api.getPrometheusMetrics(),
      ]);
      setHealth(h);
      setAlerts(a);
      setMetricsText(m);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch monitoring data.");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    const timeout = setTimeout(() => {
      void refresh();
    }, 0);
    return () => clearTimeout(timeout);
  }, [refresh]);

  const monitoringEnabled = health !== null || alerts !== null || metricsText !== null;

  return (
    <div className="flex-1 space-y-6 p-8 max-w-5xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Monitoring</h1>
          <p className="text-muted-foreground mt-1">
            Backend monitoring endpoints and Prometheus metrics.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="outline">
            {connectionState === "connected" ? "Connected" : connectionState === "checking" ? "Checking" : "Disconnected"}
          </Badge>
          <Badge variant="outline" className="max-w-[28rem] truncate">
            {connectionText}
          </Badge>
          <Button variant="outline" onClick={refresh} disabled={loading}>
            Refresh
          </Button>
        </div>
      </div>

      {error ? (
        <div className="rounded-lg border border-border/50 bg-card/50 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      <Card className="border-border/50 bg-card/50">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            Status
            <Badge variant={monitoringEnabled ? "default" : "secondary"}>
              {monitoringEnabled ? "Enabled" : "Disabled"}
            </Badge>
          </CardTitle>
          <CardDescription>
            If monitoring is disabled, the backend returns 403 for these endpoints.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm">
          {health ? (
            <div className="grid gap-2 md:grid-cols-2">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Status</span>
                <span className="font-mono">{health.status}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Uptime (s)</span>
                <span className="font-mono">{health.uptime_seconds}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Alerts enabled</span>
                <span className="font-mono">{String(health.alerts_enabled)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Prometheus enabled</span>
                <span className="font-mono">{String(health.prometheus_enabled)}</span>
              </div>
            </div>
          ) : (
            <div className="text-muted-foreground">
              {loading ? "Loading…" : "Monitoring health endpoint is unavailable (likely disabled)."}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-border/50 bg-card/50">
        <CardHeader>
          <CardTitle>Active alerts</CardTitle>
          <CardDescription>From `GET /monitoring/alerts`.</CardDescription>
        </CardHeader>
        <CardContent>
          {alerts === null ? (
            <div className="text-sm text-muted-foreground">
              {loading ? "Loading…" : "Alerts endpoint is unavailable (likely disabled)."}
            </div>
          ) : alerts.length === 0 ? (
            <div className="text-sm text-muted-foreground">No active alerts.</div>
          ) : (
            <div className="space-y-2">
              {alerts.map((a, i) => (
                <div key={i} className="rounded-lg border border-border/50 bg-background px-3 py-2 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium truncate">
                      {String(a.message ?? a.type ?? "Alert")}
                    </div>
                    <Badge variant="outline" className="shrink-0">
                      {String(a.severity ?? "unknown")}
                    </Badge>
                  </div>
                  {a.details ? (
                    <pre className="mt-2 whitespace-pre-wrap break-words text-[11px] text-muted-foreground">
                      {JSON.stringify(a.details, null, 2)}
                    </pre>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-border/50 bg-card/50">
        <CardHeader>
          <CardTitle>Prometheus metrics</CardTitle>
          <CardDescription>From `GET /metrics` (raw text).</CardDescription>
        </CardHeader>
        <CardContent>
          {metricsText === null ? (
            <div className="text-sm text-muted-foreground">
              {loading ? "Loading…" : "Metrics endpoint is unavailable (likely disabled)."}
            </div>
          ) : (
            <div className="space-y-3">
              {health?.current_metrics ? (
                <div className="grid gap-2 md:grid-cols-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Error rate</span>
                    <span className="font-mono">{formatMaybeNumber(health.current_metrics.error_rate, 4)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">P99 latency (ms)</span>
                    <span className="font-mono">{formatMaybeNumber(health.current_metrics.latency_p99_ms, 1)}</span>
                  </div>
                </div>
              ) : null}
              <pre className="max-h-[420px] overflow-auto rounded-lg border border-border/50 bg-background p-3 text-[11px] leading-relaxed">
                {metricsText}
              </pre>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

