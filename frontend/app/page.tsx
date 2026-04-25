"use client";

import { MetricCard } from "@/components/ui/metric-card";
import { Flag, Users, Activity, AlertCircle } from "lucide-react";
import { 
  Area, 
  AreaChart, 
  ResponsiveContainer, 
  Tooltip, 
  XAxis, 
  YAxis,
  CartesianGrid
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useEffect, useState } from "react";
import { api, DashboardData } from "@/lib/api";


const usageData = [
  { name: "Mon", requests: 12000, errors: 120 },
  { name: "Tue", requests: 19000, errors: 250 },
  { name: "Wed", requests: 15000, errors: 150 },
  { name: "Thu", requests: 22000, errors: 180 },
  { name: "Fri", requests: 28000, errors: 110 },
  { name: "Sat", requests: 35000, errors: 90 },
  { name: "Sun", requests: 42000, errors: 85 },
];

const recentActivity = [
  {
    id: 1,
    action: "Updated rollout",
    flag: "new-checkout-flow",
    user: "Soham Admin",
    time: "2 mins ago",
    details: "Increased from 10% to 25%",
  },
  {
    id: 2,
    action: "Toggled flag",
    flag: "dark-mode-v2",
    user: "System (AI)",
    time: "15 mins ago",
    details: "Turned ON based on positive reward (+0.85)",
  },
  {
    id: 3,
    action: "Created flag",
    flag: "pricing-tier-test",
    user: "Sarah Eng",
    time: "1 hour ago",
    details: "Initial setup",
  },
];

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [connectionState, setConnectionState] = useState<"checking" | "connected" | "disconnected">("checking");
  const [connectionText, setConnectionText] = useState("Checking backend...");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const dashboard = await api.getDashboard();
        setData(dashboard);
        const health = await api.getHealth();
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

    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const healthScore = data?.summary?.health_score ?? 0;
  const errorRate = (data?.summary?.error_rate ?? 0) * 100;
  const latency = data?.summary?.latency_p99_ms ?? 0;

  return (
    <div className="flex-1 space-y-6 p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">Overview</h1>
        <Badge
          variant="outline"
          className={
            connectionState === "connected"
              ? "border-green-500/30 text-green-600"
              : connectionState === "disconnected"
              ? "border-destructive/30 text-destructive"
              : ""
          }
        >
          {loading ? "Syncing..." : connectionText}
        </Badge>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="System Health"
          value={`${(healthScore * 100).toFixed(1)}%`}
          icon={<Flag className="h-4 w-4" />}
          trend={{ value: 2.4, label: "vs last hour", isPositive: healthScore > 0.9 }}
        />
        <MetricCard
          title="Total Evaluated Users"
          value="1.2M"
          icon={<Users className="h-4 w-4" />}
          trend={{ value: 5.4, label: "vs last week", isPositive: true }}
        />
        <MetricCard
          title="P99 Latency"
          value={`${latency.toFixed(1)}ms`}
          icon={<Activity className="h-4 w-4" />}
          trend={{ value: 2.1, label: "from baseline", isPositive: latency < 50 }}
        />
        <MetricCard
          title="Error Rate"
          value={`${errorRate.toFixed(3)}%`}
          icon={<AlertCircle className="h-4 w-4" />}
          trend={{ value: 0.05, label: "increase", isPositive: errorRate < 0.1 }}
        />
      </div>

      <div className="grid gap-6 md:grid-cols-7">
        <Card className="md:col-span-4 border-border/50 bg-card/50 backdrop-blur-sm shadow-sm">
          <CardHeader>
            <CardTitle>Evaluation Traffic</CardTitle>
            <CardDescription>
              Total flag evaluations over the last 7 days.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px] w-full min-h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={usageData}
                  margin={{ top: 5, right: 0, left: 0, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="var(--primary)" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" opacity={0.5} />
                  <XAxis 
                    dataKey="name" 
                    stroke="var(--muted-foreground)" 
                    fontSize={12} 
                    tickLine={false} 
                    axisLine={false} 
                  />
                  <YAxis 
                    stroke="var(--muted-foreground)" 
                    fontSize={12} 
                    tickLine={false} 
                    axisLine={false} 
                    tickFormatter={(value) => `${value / 1000}k`}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'var(--popover)', 
                      borderColor: 'var(--border)',
                      borderRadius: 'var(--radius)',
                      color: 'var(--popover-foreground)',
                      boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)'
                    }}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="requests" 
                    stroke="var(--primary)" 
                    strokeWidth={2}
                    fillOpacity={1} 
                    fill="url(#colorRequests)" 
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="md:col-span-3 border-border/50 bg-card/50 backdrop-blur-sm shadow-sm">
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>Latest changes across your environments.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {recentActivity.map((activity) => (
                <div key={activity.id} className="flex gap-4">
                  <div className="mt-0.5 relative">
                    <div className="h-2 w-2 rounded-full bg-primary ring-4 ring-primary/10"></div>
                    {activity.id !== recentActivity.length && (
                      <div className="absolute top-3 left-[3px] h-full w-[2px] bg-border"></div>
                    )}
                  </div>
                  <div className="flex flex-col gap-1 w-full">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-medium">{activity.action}</p>
                      <span className="text-xs text-muted-foreground">{activity.time}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-xs font-normal">
                        {activity.flag}
                      </Badge>
                      <span className="text-xs text-muted-foreground">by {activity.user}</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {activity.details}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
