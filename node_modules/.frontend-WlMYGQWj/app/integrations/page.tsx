"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { 
  MessageSquare, 
  GitGraph, 
  ExternalLink,
  RefreshCw,
  Bell
} from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const IntegrationsPage = () => {
  const [loading, setLoading] = useState(false);
  const [lastSync, setLastSync] = useState("Never");
  const [isHealthy, setIsHealthy] = useState(false);

  const syncIntegrations = async () => {
    setLoading(true);
    try {
      const [health] = await Promise.all([
        api.getHealth(),
        api.getDashboard(),
      ]);
      setIsHealthy(Boolean(health?.environment_ready));
      setLastSync(new Date().toLocaleTimeString());
    } catch (error) {
      console.error("Failed to sync integration status:", error);
      setIsHealthy(false);
      setLastSync("Sync failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const initialSync = setTimeout(() => {
      void syncIntegrations();
    }, 0);
    return () => clearTimeout(initialSync);
  }, []);

  const integrations = [
    {
      id: "slack",
      name: "Slack",
      description: "Automated rollout notifications and approval workflows.",
      icon: MessageSquare,
      status: isHealthy ? "connected" : "disconnected",
      details: isHealthy ? "Alerts can be routed through backend automation" : "Backend unavailable",
      lastSync
    },
    {
      id: "github",
      name: "GitHub",
      description: "Trigger rollouts from PRs and sync deployment status.",
      icon: GitGraph,
      status: "disconnected",
      details: "Requires OAuth",
      lastSync
    }
  ];

  return (
    <div className="flex-1 space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Integrations</h1>
          <p className="text-muted-foreground mt-1">Manage external connections and observability sync.</p>
        </div>
        <Button variant="outline" size="sm" className="rounded-full" onClick={syncIntegrations} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          {loading ? "Syncing..." : "Sync All"}
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {integrations.map((item) => (
          <Card key={item.id} className="border-border/50 bg-card/50">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted/50">
                  <item.icon className="h-6 w-6 text-primary" />
                </div>
                <Badge 
                  variant={item.status === "connected" ? "default" : "secondary"}
                  className={item.status === "connected" ? "bg-green-500/10 text-green-600 hover:bg-green-500/10" : ""}
                >
                  {item.status === "connected" ? "Connected" : "Disconnected"}
                </Badge>
              </div>
              <CardTitle className="mt-4">{item.name}</CardTitle>
              <CardDescription>{item.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Status</span>
                  <span className="font-medium">{item.details}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Last Sync</span>
                  <span className="text-xs">{item.lastSync}</span>
                </div>
                <div className="pt-4 flex gap-2">
                  <Button variant="outline" className="w-full text-xs h-8 rounded-full">
                    Configure
                  </Button>
                  <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full">
                    <ExternalLink className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="border-primary/20 bg-primary/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-primary">
            <Bell className="h-5 w-5" />
            Webhook Endpoints
          </CardTitle>
          <CardDescription>Receive automated alerts from your own infrastructure.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border bg-background/50 p-4 font-mono text-xs">
             GET {(api.getApiBaseUrl() || "http://localhost:8000")}/monitoring/alerts
          </div>
          <p className="text-[10px] text-muted-foreground mt-4">
            Uses live backend monitoring routes for alert ingestion and observability polling.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default IntegrationsPage;
