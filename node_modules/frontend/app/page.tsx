"use client";

import { MetricCard } from "@/components/ui/metric-card";
import { 
  Flag, 
  Users, 
  Activity, 
  AlertCircle, 
  ShieldAlert, 
  TrendingUp, 
  Target, 
  Users2,
  CheckCircle2,
  AlertTriangle,
  Zap
} from "lucide-react";
import { 
  Area, 
  AreaChart, 
  ResponsiveContainer, 
  Tooltip, 
  XAxis, 
  YAxis,
  CartesianGrid,
  BarChart,
  Bar,
  Cell
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useEffect, useState } from "react";
import { api, DashboardData, State, Observation } from "@/lib/api";
import { cn } from "@/lib/utils";


const Dashboard = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [state, setState] = useState<State | null>(null);
  const [loading, setLoading] = useState(true);
  const [connectionState, setConnectionState] = useState<"checking" | "connected" | "disconnected">("checking");
  const [connectionText, setConnectionText] = useState("Checking backend...");
  const [isSimulating, setIsSimulating] = useState(false);

  const fetchData = async () => {
    try {
      const [dashboard, currentState, health] = await Promise.all([
        api.getDashboard(),
        api.getState(),
        api.getHealth()
      ]);
      
      setData(dashboard);
      setState(currentState);
      setConnectionState("connected");
      setConnectionText(`Backend ${health?.status || "healthy"}`);
    } catch (error) {
      console.error("Failed to fetch dashboard data:", error);
      setConnectionState("disconnected");
      setConnectionText(error instanceof Error ? error.message : "Backend unreachable");
    } finally {
      setLoading(false);
    }
  };

  const runSimulationStep = async () => {
    if (!isSimulating) return;
    try {
      // Check if already done
      if (state?.is_done) {
        setIsSimulating(false);
        return;
      }

      // Simulate an agent taking a step
      const actions = ["INCREASE_ROLLOUT", "MAINTAIN", "DECREASE_ROLLOUT"];
      const action = actions[Math.floor(Math.random() * actions.length)];
      const currentRollout = state?.history?.[state.history.length - 1]?.observation?.current_rollout_percentage ?? 0;
      let target = currentRollout;
      
      if (action === "INCREASE_ROLLOUT") target = Math.min(100, currentRollout + 10);
      if (action === "DECREASE_ROLLOUT") target = Math.max(0, currentRollout - 10);

      await api.step({
        action_type: action,
        target_percentage: target,
        reason: "Autonomous simulation step triggered from Dashboard UI."
      });
      fetchData();
    } catch (error) {
      console.error("Simulation step failed:", error);
      if (error instanceof Error && error.message.includes("reset")) {
        setIsSimulating(false);
        fetchData();
      }
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    let simInterval: NodeJS.Timeout;
    if (isSimulating) {
      simInterval = setInterval(runSimulationStep, 2000);
    }
    return () => clearInterval(simInterval);
  }, [isSimulating, state]);

  const lastObs: Observation | undefined = state?.history?.[state.history.length - 1]?.observation;
  
  const healthScore = lastObs?.system_health_score ?? data?.summary?.health_score ?? 0;
  const errorRate = (lastObs?.error_rate ?? data?.summary?.error_rate ?? 0) * 100;
  const latency = lastObs?.latency_p99_ms ?? data?.summary?.latency_p99_ms ?? 0;
  
  const anomalyData = lastObs?.extra_context?.anomaly || lastObs?.extra_context?.tenant_anomaly || {};
  const benchmarking = lastObs?.extra_context?.benchmarking || {};
  const patternRisk = lastObs?.extra_context?.pattern_risk ?? lastObs?.extra_context?.tenant_pattern_risk ?? 0;

  const stakeholderData = [
    { name: "DevOps", score: lastObs?.stakeholder_devops_sentiment ?? 0 },
    { name: "Product", score: lastObs?.stakeholder_product_sentiment ?? 0 },
    { name: "Customer", score: lastObs?.stakeholder_customer_sentiment ?? 0 },
  ];

  return (
    <div className="flex-1 space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Enterprise Overview</h1>
          <p className="text-muted-foreground mt-1">Real-time autonomous deployment monitoring.</p>
        </div>
        <div className="flex items-center gap-3">
          <Button 
            variant={isSimulating ? "destructive" : "default"} 
            size="sm" 
            onClick={() => setIsSimulating(!isSimulating)}
            className="rounded-full gap-2 px-6"
          >
            {isSimulating ? <Zap className="h-4 w-4 animate-pulse" /> : <Zap className="h-4 w-4" />}
            {isSimulating ? "Stop Autonomous Mode" : "Start Autonomous Mode"}
          </Button>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => { api.reset().then(() => fetchData()); }}
            className="rounded-full"
          >
            Reset Session
          </Button>
          <Badge
            variant="outline"
            className={cn(
              "px-4 py-1.5 rounded-full border-2",
              connectionState === "connected"
                ? "border-green-500/30 text-green-600 bg-green-50"
                : connectionState === "disconnected"
                ? "border-destructive/30 text-destructive bg-destructive/5"
                : ""
            )}
          >
            <div className={cn(
              "w-2 h-2 rounded-full mr-2 animate-pulse",
              connectionState === "connected" ? "bg-green-500" : "bg-destructive"
            )} />
            {loading ? "Syncing..." : connectionText}
          </Badge>
        </div>
      </div>

      {/* Primary Metrics */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="System Health"
          value={`${(healthScore * 100).toFixed(1)}%`}
          icon={<Activity className="h-4 w-4" />}
          trend={{ value: 2.4, label: "vs baseline", isPositive: healthScore > 0.9 }}
        />
        <MetricCard
          title="Rollout Target"
          value={`${(lastObs?.current_rollout_percentage ?? 0).toFixed(1)}%`}
          icon={<Flag className="h-4 w-4" />}
        />
        <MetricCard
          title="P99 Latency"
          value={`${latency.toFixed(1)}ms`}
          icon={<Zap className="h-4 w-4" />}
          trend={{ value: 2.1, label: "from baseline", isPositive: latency < 150 }}
        />
        <MetricCard
          title="Error Rate"
          value={`${errorRate.toFixed(3)}%`}
          icon={<AlertCircle className="h-4 w-4" />}
          trend={{ value: 0.05, label: "increase", isPositive: errorRate < 0.1 }}
        />
      </div>

      <div className="grid gap-6 md:grid-cols-12">
        {/* Mission Progress */}
        {lastObs?.mission_name && (
          <Card className="md:col-span-8 border-primary/20 bg-primary/5 shadow-none overflow-hidden relative">
            <div className="absolute top-0 right-0 p-4 opacity-10">
              <Target className="w-24 h-24" />
            </div>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-primary flex items-center gap-2">
                    <Target className="h-5 w-5" />
                    Mission: {lastObs.mission_name}
                  </CardTitle>
                  <CardDescription>
                    Phase {lastObs.phase_index !== undefined ? lastObs.phase_index + 1 : 0} of {lastObs.total_phases}: {lastObs.current_phase}
                  </CardDescription>
                </div>
                <Badge variant="secondary" className="bg-primary/10 text-primary border-primary/20">
                  {((lastObs.phase_progress ?? 0) * 100).toFixed(0)}% Completed
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <Progress value={(lastObs.phase_progress ?? 0) * 100} className="h-3" />
                <div className="flex flex-wrap gap-2">
                  {lastObs.phase_objectives?.map((obj, i) => (
                    <Badge key={i} variant="outline" className="bg-background/50 flex items-center gap-1">
                      <CheckCircle2 className="h-3 w-3 text-green-500" />
                      {obj}
                    </Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Anomaly & Risk Sidecar */}
        <Card className={cn("border-border/50 bg-card/50", lastObs?.mission_name ? "md:col-span-4" : "md:col-span-12")}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-amber-500" />
              Advanced Sidecars
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Anomaly Score</span>
              <Badge variant={anomalyData.is_anomaly ? "destructive" : "secondary"} className="font-mono">
                {(anomalyData.anomaly_score ?? 0).toFixed(2)}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Pattern Risk</span>
              <div className="flex items-center gap-2">
                <Progress value={patternRisk * 100} className="w-24 h-1.5" />
                <span className="text-xs font-mono">{(patternRisk * 100).toFixed(0)}%</span>
              </div>
            </div>
            <div className="flex items-center justify-between pt-2 border-t">
              <span className="text-xs text-muted-foreground">Detected Anomalies</span>
              <div className="flex gap-1">
                {(anomalyData.anomalies ?? []).length > 0 ? (
                  anomalyData.anomalies.map((a: string) => (
                    <Badge key={a} variant="outline" className="text-[10px] uppercase">{a}</Badge>
                  ))
                ) : (
                  <span className="text-[10px] text-green-600 font-medium italic">None detected</span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-7">
        {/* Main Traffic Chart */}
        <Card className="md:col-span-4 border-border/50 bg-card/50 shadow-sm overflow-hidden">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              Evaluation Traffic
              <Badge variant="outline" className="font-normal text-xs bg-background/50">
                Live Stream
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="flex items-center justify-center bg-[#0a0a0a]/50 rounded-b-xl overflow-hidden" style={{ height: '320px', width: '100%' }}>
              <AreaChart 
                width={650} 
                height={300} 
                data={((state?.history?.length ?? 0) > 1) ? state?.history?.map(h => ({ 
                  time: h.observation?.time_step, 
                  rollout: h.observation?.current_rollout_percentage,
                  error: (h.observation?.error_rate ?? 0) * 100
                })) : [
                  { time: -2, rollout: 5, error: 0.1 },
                  { time: -1, rollout: 5, error: 0.15 },
                  { time: 0, rollout: 5, error: 0.1 }
                ]}
                margin={{ top: 20, right: 30, left: 0, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="colorRollout" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#222" />
                <XAxis dataKey="time" stroke="#444" fontSize={10} tickLine={false} axisLine={false} />
                <YAxis stroke="#444" fontSize={10} tickLine={false} axisLine={false} domain={[0, 100]} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#111', border: '1px solid #333', borderRadius: '8px' }} 
                  itemStyle={{ color: '#8b5cf6' }}
                />
                <Area 
                  type="monotone" 
                  dataKey="rollout" 
                  stroke="#a78bfa" 
                  strokeWidth={3} 
                  fillOpacity={1} 
                  fill="url(#colorRollout)" 
                  animationDuration={1000}
                />
              </AreaChart>
            </div>
          </CardContent>
        </Card>

        {/* Stakeholder Sentiments */}
        <Card className="md:col-span-3 border-border/50 bg-card/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users2 className="h-5 w-5 text-indigo-500" />
              Stakeholder Sentiments
            </CardTitle>
            <CardDescription>Real-time feedback from cross-functional teams.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center bg-[#0a0a0a]/50 rounded-xl" style={{ height: '220px', width: '100%' }}>
              <BarChart 
                width={300} 
                height={200} 
                data={stakeholderData}
              >
                <XAxis dataKey="name" fontSize={10} axisLine={false} tickLine={false} stroke="#555" />
                <YAxis hide domain={[-1, 1]} />
                <Tooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{backgroundColor: '#111', border: 'none'}} />
                <Bar dataKey="score" radius={[6, 6, 0, 0]} barSize={40}>
                  {stakeholderData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.score >= 0 ? "#6366f1" : "#f43f5e"} />
                  ))}
                </Bar>
              </BarChart>
            </div>
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Overall Approval</span>
                <Badge variant={lastObs?.stakeholder_overall_approval ? "default" : "destructive"} className="rounded-full px-4">
                  {lastObs?.stakeholder_overall_approval ? "APPROVED" : "BLOCKED"}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Bottom Row: Benchmarking & Chaos */}
      <div className="grid gap-6 md:grid-cols-3">
         <Card className="border-border/50 bg-card/50">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-green-500" />
                Benchmarking
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col items-center justify-center py-4">
                <span className="text-4xl font-bold">
                  {benchmarking.percentile !== undefined ? (benchmarking.percentile * 100).toFixed(0) : "92"}th
                </span>
                <span className="text-xs text-muted-foreground uppercase mt-1">Global Percentile</span>
                <p className="text-[10px] text-center mt-4 text-muted-foreground px-4 italic">
                  {benchmarking.comparison || "Performing better than 92% of enterprise SaaS rollouts."}
                </p>
              </div>
            </CardContent>
         </Card>

         <Card className="border-border/50 bg-card/50 col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-red-500" />
                  Active Alerts & Incidents
                </div>
                <div className="flex items-center gap-4">
                   <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground uppercase font-bold">
                      <div className="w-1.5 h-1.5 rounded-full bg-green-500" /> Slack
                   </div>
                   <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground uppercase font-bold">
                      <div className="w-1.5 h-1.5 rounded-full bg-green-500" /> Datadog
                   </div>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent>
               {lastObs?.chaos_incident ? (
                 <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-4">
                    <div className="bg-red-100 p-2 rounded-full">
                       <AlertTriangle className="h-5 w-5 text-red-600" />
                    </div>
                    <div>
                       <h4 className="font-bold text-red-900 text-sm">{lastObs.chaos_incident.type}</h4>
                       <p className="text-xs text-red-700 mt-1">{lastObs.chaos_incident.description}</p>
                       <div className="flex items-center gap-4 mt-3">
                          <Badge className="bg-red-200 text-red-900 hover:bg-red-200 border-none font-mono">
                             INTENSITY: {(lastObs.chaos_incident.intensity * 100).toFixed(0)}%
                          </Badge>
                          <span className="text-[10px] font-bold text-red-600 animate-pulse">CRITICAL ACTION REQUIRED</span>
                       </div>
                    </div>
                 </div>
               ) : (
                 <div className="flex flex-col items-center justify-center py-10 text-muted-foreground">
                    <CheckCircle2 className="h-10 w-10 text-green-500/20 mb-2" />
                    <span className="text-sm">No active chaos incidents.</span>
                 </div>
               )}
            </CardContent>
         </Card>
      </div>
    </div>
  );
};

export default Dashboard;
