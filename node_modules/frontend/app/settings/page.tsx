"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Key, Globe, Webhook, Save } from "lucide-react";
import { api } from "@/lib/api";
import * as React from "react";

export default function SettingsPage() {
  const [apiKey, setApiKey] = React.useState(() => api.getApiKey() || "");
  const [apiBaseUrl, setApiBaseUrl] = React.useState(() => api.getApiBaseUrl() || "");
  const [status, setStatus] = React.useState<string>("");

  const handleSaveKey = () => {
    api.setApiKey(apiKey);
    setStatus("API key saved.");
  };

  const handleSaveBaseUrl = () => {
    if (!apiBaseUrl.trim()) {
      setStatus("API base URL cannot be empty.");
      return;
    }
    api.setApiBaseUrl(apiBaseUrl);
    setStatus("API base URL saved.");
  };

  const handleTestConnection = async () => {
    setStatus("Testing backend connection...");
    try {
      const health = await api.getHealth();
      const ready = health?.environment_ready ? "ready" : "not ready";
      setStatus(`Backend connected (${health?.status || "unknown"}, ${ready}).`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Connection failed";
      setStatus(`Connection failed: ${message}`);
    }
  };

  return (
    <div className="flex-1 space-y-6 p-8 max-w-5xl">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground mt-1">Manage platform configuration and integrations.</p>
      </div>

      <div className="grid gap-6">
        <Card className="border-border/50 bg-card/50 backdrop-blur-sm shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="h-5 w-5 text-primary" /> API Keys
            </CardTitle>
            <CardDescription>
              Keys for connecting your applications to the FeatureFlag platform.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="backend-key">Backend Simulation Key (X-API-Key)</Label>
              <div className="flex gap-2">
                <Input 
                  id="backend-key" 
                  type="password"
                  value={apiKey} 
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="ff_live_..."
                  className="font-mono" 
                />
                <Button onClick={handleSaveKey}>
                  <Save className="mr-2 h-4 w-4" /> Save
                </Button>
              </div>
              <p className="text-[10px] text-muted-foreground">Used for all simulation and monitoring API calls.</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="api-base-url">Frontend API Base URL</Label>
              <div className="flex gap-2">
                <Input
                  id="api-base-url"
                  value={apiBaseUrl}
                  onChange={(e) => setApiBaseUrl(e.target.value)}
                  placeholder="http://127.0.0.1:8000"
                  className="font-mono"
                />
                <Button variant="outline" onClick={handleSaveBaseUrl}>Save URL</Button>
                <Button variant="outline" onClick={handleTestConnection}>Test</Button>
              </div>
              <p className="text-[10px] text-muted-foreground">Overrides NEXT_PUBLIC_API_URL in browser for this machine.</p>
            </div>
            
            <div className="space-y-2 pt-4 opacity-50">
              <Label htmlFor="prod-key">Production Server Key (Read-only)</Label>
              <div className="flex gap-2">
                <Input id="prod-key" defaultValue="ff_live_*************************" readOnly className="font-mono text-muted-foreground bg-muted/20" />
                <Button variant="outline" disabled>Copy</Button>
              </div>
            </div>
          </CardContent>
          <CardFooter className="bg-muted/20 border-t border-border/50">
            <div className="flex w-full items-center justify-between gap-3">
              <Button
                variant="ghost"
                className="text-xs text-muted-foreground"
                onClick={() => window.open("https://nextjs.org/docs/app/guides/environment-variables", "_blank")}
              >
                Need help finding your key? Check the documentation.
              </Button>
              {status ? <Badge variant="outline">{status}</Badge> : null}
            </div>
          </CardFooter>
        </Card>

        <Card className="border-border/50 bg-card/50 backdrop-blur-sm shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-5 w-5 text-primary" /> Environments
            </CardTitle>
            <CardDescription>
              Configure targeting environments for your flags.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-background">
                <div>
                  <p className="font-medium">Production</p>
                  <p className="text-xs text-muted-foreground">Live environment</p>
                </div>
                <Badge variant="default">Default</Badge>
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-background">
                <div>
                  <p className="font-medium">Staging</p>
                  <p className="text-xs text-muted-foreground">Pre-production testing</p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setStatus("Staging environment editing will be added in the next update.")}>Edit</Button>
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-background">
                <div>
                  <p className="font-medium">Development</p>
                  <p className="text-xs text-muted-foreground">Local development</p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setStatus("Development environment editing will be added in the next update.")}>Edit</Button>
              </div>
            </div>
          </CardContent>
          <CardFooter className="bg-muted/20 border-t border-border/50">
            <Button variant="outline" className="ml-auto mt-4" onClick={() => setStatus("Environment creation is queued for a future release.")}>Add Environment</Button>
          </CardFooter>
        </Card>

        <Card className="border-border/50 bg-card/50 backdrop-blur-sm shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Webhook className="h-5 w-5 text-primary" /> Integrations
            </CardTitle>
            <CardDescription>
              Connect to external services like Slack and GitHub.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between p-4 rounded-lg border border-border/50 bg-background">
              <div className="flex items-center gap-4">
                <div className="h-10 w-10 bg-purple-500/10 rounded-lg flex items-center justify-center">
                  <span className="font-bold text-purple-600">SL</span>
                </div>
                <div>
                  <p className="font-medium">Slack</p>
                  <p className="text-sm text-muted-foreground">Send rollout and incident notifications.</p>
                </div>
              </div>
              <Button variant="outline" onClick={() => setStatus("Slack integration setup is currently a guided/manual step.")}>Connect</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
