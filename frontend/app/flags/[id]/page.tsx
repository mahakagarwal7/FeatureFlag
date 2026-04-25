"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, Save, History, Activity, Split, Users } from "lucide-react";
import { AnimatedToggle } from "@/components/ui/animated-toggle";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

const usageData = [
  { time: "10:00", eval: 400, success: 380 },
  { time: "10:05", eval: 430, success: 420 },
  { time: "10:10", eval: 450, success: 440 },
  { time: "10:15", eval: 420, success: 410 },
  { time: "10:20", eval: 500, success: 480 },
  { time: "10:25", eval: 520, success: 500 },
  { time: "10:30", eval: 600, success: 590 },
];

export default function FlagDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  
  const [isOn, setIsOn] = useState(true);
  const [rollout, setRollout] = useState([25]);
  const [hasChanges, setHasChanges] = useState(false);
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    const fetchState = async () => {
      try {
        const state = await api.getState();
        
        // If this is the backend flag, sync state
        const history = state.history || [];
        const lastHistory = history.length > 0 ? history[history.length - 1] : null;
        const observation = lastHistory?.observation;
        
        if (observation && observation.feature_name === id) {
          setIsOn(!state.is_done);
          setRollout([observation.current_rollout_percentage]);
        }
      } catch (error) {
        console.error("Failed to fetch flag detail:", error);
      }
    };
    fetchState();
  }, [id]);

  const handleRolloutChange = (val: number | number[] | readonly number[]) => {
    const newVal = typeof val === 'number' ? val : val[0];
    setRollout([newVal]);
    setHasChanges(true);
  };

  const handleToggle = (state: boolean) => {
    setIsOn(state);
    setHasChanges(true);
  };

  const handleSave = async () => {
    try {
      const freshState = await api.getState();
      const history = freshState.history || [];
      const currentRollout = history.length > 0 
        ? history[history.length - 1]?.observation?.current_rollout_percentage ?? 0
        : 0;
      const targetRollout = rollout[0];
      
      let action_type = "MAINTAIN";
      if (!isOn) {
        action_type = "ROLLBACK";
      } else if (targetRollout > currentRollout) {
        action_type = "INCREASE_ROLLOUT";
      } else if (targetRollout < currentRollout) {
        action_type = "DECREASE_ROLLOUT";
      } else if (targetRollout === 100) {
        action_type = "FULL_ROLLOUT";
      } else if (targetRollout === 0) {
        action_type = "HALT_ROLLOUT";
      }

      await api.step({
        action_type,
        target_percentage: targetRollout,
        reason: `Manual override via dashboard for ${id}`
      });
      
      setHasChanges(false);
      await api.getState();
    } catch (error) {
      console.error("Failed to save changes:", error);
    }
  };

  return (
    <div className="flex-1 space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()} className="rounded-full hover:bg-muted">
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold tracking-tight capitalize">{id.replace(/-/g, ' ')}</h1>
              <Badge variant={isOn ? "default" : "secondary"} className="rounded-full">
                {isOn ? "Active" : "Inactive"}
              </Badge>
            </div>
            <p className="text-muted-foreground mt-1 text-sm font-mono">{id}</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            className="rounded-full border-border/50 bg-card/50"
            onClick={() => setMessage("Audit log UI is not yet exposed in frontend. Backend audit endpoints remain available.")}
          >
            <History className="mr-2 h-4 w-4" />
            Audit Log
          </Button>
          {hasChanges && (
            <Button onClick={handleSave} className="rounded-full bg-primary shadow-md shadow-primary/20">
              <Save className="mr-2 h-4 w-4" />
              Save Changes
            </Button>
          )}
        </div>
      </div>

      {message ? (
        <div className="rounded-lg border border-border/50 bg-card/50 px-4 py-3 text-sm text-muted-foreground">
          {message}
        </div>
      ) : null}

      <div className="grid gap-6 md:grid-cols-3">
        <div className="md:col-span-2 space-y-6">
          <Card className="border-border/50 bg-card/50 backdrop-blur-sm shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Configuration</CardTitle>
                <CardDescription>Manage how this flag is evaluated.</CardDescription>
              </div>
              <AnimatedToggle isOn={isOn} onToggle={handleToggle} />
            </CardHeader>
            <CardContent className="space-y-8">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-semibold text-sm">Percentage Rollout</h4>
                    <p className="text-xs text-muted-foreground">Serve this flag to a random subset of users.</p>
                  </div>
                  <span className="text-2xl font-bold text-primary">{rollout[0]}%</span>
                </div>
                <Slider 
                  value={rollout} 
                  onValueChange={handleRolloutChange} 
                  max={100} 
                  step={1} 
                  disabled={!isOn}
                  className="py-4"
                />
              </div>

              <div className="pt-6 border-t border-border/50">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h4 className="font-semibold text-sm">Targeting Rules</h4>
                    <p className="text-xs text-muted-foreground">Override rollout for specific users or segments.</p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-full h-8"
                    onClick={() => setMessage("Rule builder UI is planned. Current rollout and toggle controls remain fully functional.")}
                  >
                    Add Rule
                  </Button>
                </div>
                
                <div className="rounded-lg border border-border/50 bg-muted/30 p-4">
                  <div className="flex items-center gap-3 text-sm">
                    <span className="font-medium">IF</span>
                    <Badge variant="secondary" className="rounded-md">email</Badge>
                    <span className="text-muted-foreground">ends with</span>
                    <Badge variant="outline" className="rounded-md bg-background">@acme.com</Badge>
                    <span className="font-medium ml-2">THEN</span>
                    <Badge variant="default" className="rounded-md bg-green-500/20 text-green-500 hover:bg-green-500/30">TRUE</Badge>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/50 bg-card/50 backdrop-blur-sm shadow-sm">
            <CardHeader>
              <CardTitle>Live Metrics</CardTitle>
              <CardDescription>Real-time evaluation data for the last 30 minutes.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-[250px] w-full min-h-[250px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={usageData} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorEval" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="var(--primary)" stopOpacity={0}/>
                      </linearGradient>
                      <linearGradient id="colorSuccess" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" opacity={0.5} />
                    <XAxis dataKey="time" stroke="var(--muted-foreground)" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke="var(--muted-foreground)" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: 'var(--popover)', 
                        borderColor: 'var(--border)',
                        borderRadius: 'var(--radius)',
                      }}
                    />
                    <Area type="monotone" dataKey="eval" name="Total Evals" stroke="var(--primary)" fillOpacity={1} fill="url(#colorEval)" />
                    <Area type="monotone" dataKey="success" name="Served TRUE" stroke="#10b981" fillOpacity={1} fill="url(#colorSuccess)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="border-border/50 bg-card/50 backdrop-blur-sm shadow-sm">
            <CardHeader>
              <CardTitle>Variants</CardTitle>
              <CardDescription>A/B testing configuration.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-3 rounded-lg border border-primary/20 bg-primary/5">
                <div className="flex items-center gap-3">
                  <div className="h-2 w-2 rounded-full bg-primary" />
                  <span className="font-medium text-sm">Control (False)</span>
                </div>
                <span className="text-sm text-muted-foreground">{100 - rollout[0]}%</span>
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-muted/20">
                <div className="flex items-center gap-3">
                  <div className="h-2 w-2 rounded-full bg-green-500" />
                  <span className="font-medium text-sm">Treatment (True)</span>
                </div>
                <span className="text-sm font-medium">{rollout[0]}%</span>
              </div>
              <Button
                variant="ghost"
                className="w-full text-xs"
                size="sm"
                onClick={() => setMessage("Multivariate option editor will be added in a future update.")}
              >
                <Split className="mr-2 h-3 w-3" />
                Add Multivariate Option
              </Button>
            </CardContent>
          </Card>

          <Card className="border-border/50 bg-card/50 backdrop-blur-sm shadow-sm">
            <CardHeader>
              <CardTitle>Quick Stats</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <Users className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Unique Users (24h)</p>
                  <p className="text-xl font-bold">12.4k</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-500/10 text-green-500">
                  <Activity className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Success Rate</p>
                  <p className="text-xl font-bold">99.98%</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
