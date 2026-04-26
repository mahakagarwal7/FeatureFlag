"use client";

import { useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Search, MoreHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { useEnv } from "@/components/env/env-provider";

export default function FeatureFlagsPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const { state } = useEnv();

  const backendFlag = useMemo(() => {
    const lastObs = state?.history?.[state.history.length - 1]?.observation;
    if (!lastObs) return null;
    return {
      id: lastObs.feature_name,
      name: lastObs.feature_name.replace(/_/g, " "),
      rollout: lastObs.current_rollout_percentage,
      status: !(state?.is_done ?? false),
      scenario: state?.scenario_name ?? "unknown",
      difficulty: state?.difficulty ?? "unknown",
      lastUpdated: `Step ${state?.step_count ?? 0}`,
    };
  }, [state]);

  const filtered = useMemo(() => {
    if (!backendFlag) return [];
    const q = searchQuery.trim().toLowerCase();
    if (!q) return [backendFlag];
    if (backendFlag.id.toLowerCase().includes(q) || backendFlag.name.toLowerCase().includes(q)) {
      return [backendFlag];
    }
    return [];
  }, [backendFlag, searchQuery]);

  return (
    <div className="flex-1 space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Control</h1>
          <p className="text-muted-foreground mt-1">The UI reflects only what the backend supports.</p>
        </div>
        <Button variant="outline" className="rounded-full" onClick={() => router.push("/monitoring")}>
          View monitoring
        </Button>
      </div>

      <div className="flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input 
            placeholder="Search…" 
            className="pl-9 rounded-full bg-card/50 backdrop-blur-sm border-border/50"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <div className="grid gap-4 mt-6">
        {filtered.map((flag) => (
          <Card 
            key={flag.id} 
            className="border-border/50 bg-card/50 backdrop-blur-sm hover:border-primary/30 hover:shadow-md transition-all cursor-pointer group"
            onClick={() => router.push(`/flags/${flag.id}`)}
          >
            <CardContent className="p-0 flex items-center justify-between">
              <div className="p-6 flex items-center gap-6 flex-1">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h3 className="font-semibold text-lg">{flag.name}</h3>
                    <Badge variant={flag.status ? "default" : "secondary"} className="rounded-full text-xs font-medium">
                      {flag.status ? "Active" : "Done"}
                    </Badge>
                    <Badge variant="outline" className="rounded-full text-xs font-medium bg-background/50">
                      {flag.rollout}% Rollout
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">
                    Scenario: {flag.scenario} ({flag.difficulty})
                  </p>
                </div>
                
                <div className="flex items-center gap-6">
                  <div className="flex flex-col items-end">
                    <span className="text-sm font-medium">{flag.lastUpdated}</span>
                    <span className="text-xs text-muted-foreground">Last updated</span>
                  </div>
                  
                  <Button
                    variant="ghost"
                    size="icon"
                    className="opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={(e) => {
                      e.stopPropagation();
                      router.push(`/flags/${flag.id}`);
                    }}
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {!backendFlag ? (
          <Card className="border-border/50 bg-card/50">
            <CardContent className="p-6 text-sm text-muted-foreground">
              No active simulation found yet. Start the backend and open the Dashboard to initialize state.
            </CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  );
}
