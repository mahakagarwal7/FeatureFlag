"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BrainCircuit, Zap, ShieldCheck } from "lucide-react";
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from "recharts";

import { useEffect, useState } from "react";
import { api, State } from "@/lib/api";

export default function AIDecisionsPage() {
  const [state, setState] = useState<State | null>(null);

  useEffect(() => {
    const fetchState = async () => {
      try {
        const s = await api.getState();
        setState(s);
      } catch (error) {
        console.error("Failed to fetch AI state:", error);
      }
    };
    fetchState();
    const interval = setInterval(fetchState, 5000);
    return () => clearInterval(interval);
  }, []);

  const rewardData = (state?.history || []).map((step, index: number) => ({
    episode: index + 1,
    reward: Number(step.reward ?? 0)
  }));

  const totalReward = state?.total_reward ?? 0;
  const currentStep = state?.step_count ?? 0;
  return (
    <div className="flex-1 space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">AI Decision Panel</h1>
          <p className="text-muted-foreground mt-1">Monitor Reinforcement Learning (RL) agent performance.</p>
        </div>
        <Badge variant="outline" className="bg-primary/5 text-primary border-primary/20 px-3 py-1">
          <BrainCircuit className="mr-2 h-4 w-4" />
          Agent Active
        </Badge>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card className="border-border/50 bg-card/50 backdrop-blur-sm shadow-sm md:col-span-2">
          <CardHeader>
            <CardTitle>Session Reward Track</CardTitle>
            <CardDescription>Reward progression for the current episode: {state?.episode_id || "N/A"}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px] w-full min-h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rewardData} margin={{ top: 5, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" opacity={0.5} />
                  <XAxis dataKey="episode" stroke="var(--muted-foreground)" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="var(--muted-foreground)" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'var(--popover)', 
                      borderColor: 'var(--border)',
                      borderRadius: 'var(--radius)',
                    }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="reward" 
                    stroke="var(--primary)" 
                    strokeWidth={3} 
                    dot={{ r: 4, fill: "var(--background)", strokeWidth: 2 }} 
                    activeDot={{ r: 6, fill: "var(--primary)" }} 
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="border-border/50 bg-card/50 backdrop-blur-sm shadow-sm">
            <CardHeader>
              <CardTitle>Agent Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Cumulative Reward</span>
                <span className="font-medium text-sm text-primary">{totalReward.toFixed(2)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Current Step</span>
                <span className="font-medium text-sm">{currentStep}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Scenario</span>
                <span className="font-medium text-sm truncate ml-2">{state?.scenario_name || "N/A"}</span>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/50 bg-card/50 backdrop-blur-sm shadow-sm">
            <CardHeader>
              <CardTitle>Recent Interventions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-3 text-sm">
                <Zap className="h-4 w-4 text-yellow-500 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium">Halted rollout: &apos;new-checkout&apos;</p>
                  <p className="text-xs text-muted-foreground">Error rate spike detected (2.4%)</p>
                </div>
              </div>
              <div className="flex gap-3 text-sm">
                <ShieldCheck className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium">Scaled: &apos;cache-v2&apos;</p>
                  <p className="text-xs text-muted-foreground">Latency improved by 40ms. Scaled to 100%.</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
