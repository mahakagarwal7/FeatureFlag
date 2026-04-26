"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BrainCircuit, Zap, MessageSquare, History, Activity } from "lucide-react";
import { 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  AreaChart,
  Area
} from "recharts";

import { useEffect, useState } from "react";
import { api, State } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function AIDecisionsPage() {
  const [state, setState] = useState<State | null>(null);

  const fetchState = async () => {
    try {
      const s = await api.getState();
      setState(s);
    } catch (error) {
      console.error("Failed to fetch AI state:", error);
    }
  };

  useEffect(() => {
    const initialFetch = setTimeout(() => {
      void fetchState();
    }, 0);
    const interval = setInterval(fetchState, 5000);
    return () => {
      clearTimeout(initialFetch);
      clearInterval(interval);
    };
  }, []);

  const history = state?.history || [];
  const rewardData = history.map((step, index: number) => ({
    episode: index + 1,
    reward: Number(step.reward ?? 0)
  }));

  const rolloutData = history.map((step, index: number) => ({
    episode: index + 1,
    rollout: step.observation?.current_rollout_percentage ?? 0
  }));

  const totalReward = state?.total_reward ?? 0;
  const currentStep = state?.step_count ?? 0;
  
  // Get recent decisions from history
  const recentDecisions = [...history].reverse().slice(0, 10).filter(h => h.action);

  return (
    <div className="flex-1 space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">AI Control Center</h1>
          <p className="text-muted-foreground mt-1">Real-time Reinforcement Learning (RL) performance & reasoning.</p>
        </div>
        <div className="flex items-center gap-4">
           <Badge variant="outline" className="bg-primary/5 text-primary border-primary/20 px-3 py-1 animate-pulse">
            <BrainCircuit className="mr-2 h-4 w-4" />
            Agent: PPO-Master
          </Badge>
          <Badge variant={state?.is_done ? "secondary" : "default"} className="px-3 py-1">
            {state?.is_done ? "SESSION COMPLETE" : "LEARNING IN PROGRESS"}
          </Badge>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-12">
        <Card className="border-border/50 bg-card/50 shadow-sm md:col-span-8">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Decision Reward & Rollout</CardTitle>
              <CardDescription>Performance tracking for episode: {state?.episode_id || "N/A"}</CardDescription>
            </div>
            <div className="flex gap-4 text-xs font-medium uppercase text-muted-foreground">
               <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-primary" /> Reward</div>
               <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-indigo-400" /> Rollout %</div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="h-[350px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={rewardData.map((d, i) => ({ ...d, rollout: rolloutData[i]?.rollout }))}>
                  <defs>
                    <linearGradient id="colorReward" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.1}/>
                      <stop offset="95%" stopColor="var(--primary)" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" opacity={0.3} />
                  <XAxis dataKey="episode" stroke="var(--muted-foreground)" fontSize={10} tickLine={false} axisLine={false} />
                  <YAxis yAxisId="left" stroke="var(--muted-foreground)" fontSize={10} tickLine={false} axisLine={false} />
                  <YAxis yAxisId="right" orientation="right" stroke="var(--muted-foreground)" fontSize={10} tickLine={false} axisLine={false} domain={[0, 100]} />
                  <Tooltip />
                  <Area 
                    yAxisId="left"
                    type="monotone" 
                    dataKey="reward" 
                    stroke="var(--primary)" 
                    strokeWidth={2} 
                    fill="url(#colorReward)"
                  />
                  <Line 
                    yAxisId="right"
                    type="stepAfter" 
                    dataKey="rollout" 
                    stroke="#818cf8" 
                    strokeWidth={2} 
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <div className="md:col-span-4 space-y-6">
          <Card className="border-border/50 bg-card/50 shadow-sm">
            <CardHeader>
              <CardTitle className="text-sm font-medium">Session Metrics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Cumulative Reward</span>
                <span className="font-bold text-lg text-primary">{totalReward.toFixed(2)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Steps/Iteration</span>
                <span className="font-medium text-sm">{currentStep}</span>
              </div>
              <div className="flex items-center justify-between border-t pt-4">
                <div className="flex flex-col">
                   <span className="text-xs text-muted-foreground uppercase font-bold tracking-wider">Scenario</span>
                   <span className="font-medium text-sm truncate">{state?.scenario_name || "N/A"}</span>
                </div>
                <Badge variant="outline" className="bg-muted/50">{state?.difficulty}</Badge>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/50 bg-card/50 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Zap className="h-4 w-4 text-yellow-500" />
                Live Intervention
              </CardTitle>
            </CardHeader>
            <CardContent>
               <div className="p-3 rounded-lg bg-background/50 border border-border/50">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold text-muted-foreground">LAST ACTION</span>
                    <Badge variant="outline" className="text-[10px] bg-primary/5 text-primary border-primary/20">
                       {recentDecisions[0]?.action?.action_type || "WAITING"}
                    </Badge>
                  </div>
                  <p className="text-xs leading-relaxed italic text-muted-foreground">
                    &quot;{recentDecisions[0]?.action?.reason || "Observing system baseline..."}&quot;
                  </p>
               </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <Card className="border-border/50 bg-card/50 shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <History className="h-5 w-5 text-indigo-500" />
              Agent Reasoning Log
            </CardTitle>
            <CardDescription>Step-by-step trace of autonomous decisions and feedback.</CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-0">
             {recentDecisions.length > 0 ? (
               recentDecisions.map((step, i) => (
                 (() => {
                   const actionType = step.action?.action_type ?? "MAINTAIN";
                   const targetPercentage = step.action?.target_percentage ?? 0;
                   const reason = step.action?.reason ?? "No reasoning provided.";
                   return (
                 <div key={i} className="flex gap-4 border-b border-border/30 last:border-0 py-4 group">
                    <div className="flex flex-col items-center">
                       <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center text-[10px] font-bold">
                          #{history.length - i}
                       </div>
                       <div className="flex-1 w-[1px] bg-border my-2" />
                    </div>
                    <div className="flex-1 space-y-2">
                       <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                             <Badge className={cn(
                               "text-[10px] font-bold",
                               actionType.includes("INCREASE") ? "bg-green-100 text-green-700 hover:bg-green-100" :
                               actionType.includes("ROLLBACK") || actionType.includes("HALT") ? "bg-red-100 text-red-700 hover:bg-red-100" :
                               "bg-blue-100 text-blue-700 hover:bg-blue-100"
                             )}>
                                {actionType}
                             </Badge>
                             <span className="text-sm font-bold">{targetPercentage}% Rollout Target</span>
                          </div>
                          <div className="flex items-center gap-2">
                             <Badge variant="outline" className={cn(
                               "text-[10px] font-mono",
                               (step.reward ?? 0) > 0 ? "text-green-600 border-green-200" : "text-red-600 border-red-200"
                             )}>
                                REWARD: {(step.reward ?? 0) > 0 ? "+" : ""}{(step.reward ?? 0).toFixed(2)}
                             </Badge>
                          </div>
                       </div>
                       <div className="flex items-start gap-2 bg-muted/30 p-2.5 rounded-lg">
                          <MessageSquare className="h-3 w-3 text-muted-foreground mt-1 shrink-0" />
                          <p className="text-xs text-muted-foreground leading-normal">
                             {reason}
                          </p>
                       </div>
                       <div className="flex items-center gap-4 pt-1">
                          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                             <Activity className="h-3 w-3" />
                             Health: {((step.observation?.system_health_score ?? 0) * 100).toFixed(1)}%
                          </div>
                          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                             <Zap className="h-3 w-3" />
                             Latency: {(step.observation?.latency_p99_ms ?? 0).toFixed(0)}ms
                          </div>
                       </div>
                    </div>
                 </div>
                   );
                 })()
               ))
             ) : (
               <div className="py-20 text-center text-muted-foreground flex flex-col items-center gap-4">
                  <History className="h-12 w-12 opacity-10" />
                  <p className="text-sm">No decisions logged in this session yet.</p>
               </div>
             )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
