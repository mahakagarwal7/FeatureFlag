"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Beaker, Plus, ArrowRight, BarChart2, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

import { useEffect, useState } from "react";
import { api, State } from "@/lib/api";

export default function ExperimentsPage() {
  const [state, setState] = useState<State | null>(null);
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    const fetchState = async () => {
      try {
        const s = await api.getState();
        setState(s);
      } catch (error) {
        console.error("Failed to fetch experiments:", error);
      }
    };
    fetchState();
  }, []);

  const history = state?.history || [];
  const lastHistory = history.length > 0 ? history[history.length - 1] : null;
  const observation = lastHistory?.observation;
  const reward = lastHistory?.reward ?? 0;
  const rollout = observation?.current_rollout_percentage ?? 0;

  return (
    <div className="flex-1 space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Experiments</h1>
          <p className="text-muted-foreground mt-1">A/B tests and multivariate experiments.</p>
        </div>
        <Button
          className="rounded-full shadow-md shadow-primary/20"
          onClick={() => setMessage("Experiment creation wizard is coming next. Existing backend simulation remains unchanged.")}
        >
          <Plus className="mr-2 h-4 w-4" />
          New Experiment
        </Button>
      </div>

      {message ? (
        <div className="rounded-lg border border-border/50 bg-card/50 px-4 py-3 text-sm text-muted-foreground">
          {message}
        </div>
      ) : null}

      <div className="grid gap-6">
        {/* Live Simulation Card */}
        {observation && (
          <Card className="glassy-card group border-primary/30 shadow-lg shadow-primary/5 transition-all cursor-pointer">
            <CardContent className="p-6">
              <div className="flex flex-col md:flex-row gap-6 md:items-center justify-between">
                <div className="flex items-start gap-4 flex-1">
                  <div className="h-12 w-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0 mt-1 shadow-inner border border-primary/20">
                    <Zap className="h-6 w-6" />
                  </div>
                  <div>
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-bold">Live RL Simulation: {observation.feature_name}</h3>
                      <Badge variant="default" className="bg-green-500/10 text-green-500 hover:bg-green-500/20 shadow-none border-0 px-2 py-0.5 animate-pulse">Active</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">Current rollout being managed by the AI agent in {state?.scenario_name}.</p>
                    
                    <div className="flex items-center gap-8 mt-6">
                      <div className="space-y-1">
                        <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Rollout</p>
                        <p className="text-sm font-bold">{rollout}%</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Reward</p>
                        <p className={cn("text-sm font-bold", reward >= 0 ? "text-green-500" : "text-destructive")}>
                          {reward >= 0 ? "+" : ""}{reward.toFixed(4)}
                        </p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">System Health</p>
                        <p className="text-sm font-bold">{(observation.system_health_score * 100).toFixed(1)}%</p>
                      </div>
                    </div>
                  </div>
                </div>
                
                <div className="flex flex-col items-end gap-4 min-w-[240px]">
                  <div className="w-full space-y-2">
                    <div className="flex justify-between text-[10px] font-bold uppercase tracking-tighter">
                      <span>Baseline</span>
                      <span>Target ({rollout}%)</span>
                    </div>
                    <div className="w-full bg-muted rounded-full h-3 overflow-hidden flex relative shadow-inner">
                      <div 
                        className="bg-muted-foreground/20 h-full transition-all duration-500" 
                        style={{ width: `${100 - rollout}%` }} 
                      />
                      <div 
                        className="progress-gradient h-full transition-all duration-500 relative" 
                        style={{ width: `${rollout}%` }}
                      >
                        <div className="absolute inset-0 animate-shimmer" />
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center justify-between w-full text-xs">
                    <div className="flex flex-col">
                      <span className="text-muted-foreground">Error Rate</span>
                      <span className="font-medium">{(observation.error_rate * 100).toFixed(2)}%</span>
                    </div>
                    <div className="flex flex-col items-end">
                      <span className="text-muted-foreground">P99 Latency</span>
                      <span className="font-bold text-primary text-sm">{observation.latency_p99_ms.toFixed(1)}ms</span>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}        <Card className="glassy-card group hover:border-primary/30 transition-all cursor-pointer">
          <CardContent className="p-6">
            <div className="flex flex-col md:flex-row gap-6 md:items-center justify-between">
              <div className="flex items-start gap-4 flex-1">
                <div className="h-12 w-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0 mt-1 shadow-inner">
                  <Beaker className="h-6 w-6" />
                </div>
                <div>
                  <div className="flex items-center gap-3">
                    <h3 className="text-lg font-bold">Pricing Page Redesign</h3>
                    <Badge variant="default" className="bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20 shadow-none border-0 px-2 py-0.5">Running</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">Testing new annual vs monthly toggle placement.</p>
                  
                  <div className="flex items-center gap-8 mt-6">
                    <div className="space-y-1">
                      <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Traffic Allocation</p>
                      <p className="text-sm font-bold">50/50 Split</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Primary Metric</p>
                      <p className="text-sm font-bold">Conversion to Paid</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Participants</p>
                      <p className="text-sm font-bold">45,210</p>
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="flex flex-col items-end gap-4 min-w-[240px]">
                <div className="w-full space-y-2">
                  <div className="flex justify-between text-[10px] font-bold uppercase tracking-tighter">
                    <span>Control</span>
                    <span>Variant</span>
                  </div>
                  <div className="w-full bg-muted rounded-full h-3 overflow-hidden flex relative shadow-inner">
                    <div className="progress-gradient h-full w-[45%] relative">
                      <div className="absolute inset-0 animate-shimmer" />
                    </div>
                    <div className="bg-green-500 h-full w-[55%] relative">
                      <div className="absolute inset-0 animate-shimmer" />
                    </div>
                  </div>
                </div>
                <div className="flex items-center justify-between w-full text-xs">
                  <div className="flex flex-col">
                    <span className="text-muted-foreground">4.2% cvr</span>
                  </div>
                  <div className="flex flex-col items-end">
                    <span className="font-bold text-green-500 text-sm">5.1% cvr</span>
                    <span className="text-[10px] text-green-500/70">+21% lift</span>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-2 text-primary group-hover:bg-primary/5"
                  onClick={() => setMessage("Detailed result analytics page is not yet implemented in this build.")}
                >
                  View Results <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="glassy-card group hover:border-primary/30 transition-all cursor-pointer">
          <CardContent className="p-6">
            <div className="flex flex-col md:flex-row gap-6 md:items-center justify-between">
              <div className="flex items-start gap-4 flex-1">
                <div className="h-12 w-12 rounded-xl bg-muted text-muted-foreground flex items-center justify-center shrink-0 mt-1 shadow-inner">
                  <BarChart2 className="h-6 w-6" />
                </div>
                <div>
                  <div className="flex items-center gap-3">
                    <h3 className="text-lg font-bold text-muted-foreground">Onboarding Flow v3</h3>
                    <Badge variant="secondary" className="px-2 py-0.5">Completed</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">Simplified 3-step onboarding process.</p>
                </div>
              </div>
              
              <div className="flex flex-col items-end">
                <p className="text-sm font-bold text-green-500 bg-green-500/10 px-2 py-1 rounded-md tracking-tight">+12.4% Completion Rate</p>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mt-2 font-semibold">Winner deployed 2 weeks ago</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
