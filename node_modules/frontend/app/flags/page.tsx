"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { AnimatedToggle } from "@/components/ui/animated-toggle";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Search, Filter, Plus, MoreHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { api, State } from "@/lib/api";

const mockFlags = [
  // ... (keeping some mock flags for variety)
  {
    id: "dark-mode-v2",
    name: "Dark Mode V2",
    description: "Updated dark mode palette with higher contrast.",
    status: true,
    rollout: 100,
    environment: "Production",
    lastUpdated: "15 mins ago"
  },
  {
    id: "pricing-tier-test",
    name: "Pricing Tier Test",
    description: "A/B testing new pricing tier names.",
    status: false,
    rollout: 0,
    environment: "Development",
    lastUpdated: "1 hour ago"
  }
];

export default function FeatureFlagsPage() {
  const router = useRouter();
  const [flags, setFlags] = useState(mockFlags);
  const [searchQuery, setSearchQuery] = useState("");
  const [backendState, setBackendState] = useState<State | null>(null);
  const [activeOnly, setActiveOnly] = useState(false);

  useEffect(() => {
    const fetchBackendState = async () => {
      try {
        const state = await api.getState();
        setBackendState(state);
      } catch (error) {
        console.error("Failed to fetch backend state:", error);
      }
    };
    fetchBackendState();
  }, []);

  const handleToggle = (id: string, newState: boolean) => {
    setFlags(flags.map(f => f.id === id ? { ...f, status: newState } : f));
  };

  // Merge backend state into flags list
  const allFlags = [...flags];
  if (backendState) {
    const history = backendState.history || [];
    const lastHistory = history.length > 0 ? history[history.length - 1] : null;
    const observation = lastHistory?.observation;
    
    // Check if it already exists in mock (it shouldn't by ID)
    const exists = allFlags.find(f => f.id === observation?.feature_name);
    if (!exists && observation) {
      allFlags.unshift({
        id: observation.feature_name,
        name: observation.feature_name.replace(/_/g, ' '),
        description: `Autonomous rollout mission in ${backendState.scenario_name} (${backendState.difficulty})`,
        status: !backendState.is_done,
        rollout: observation.current_rollout_percentage,
        environment: "Production",
        lastUpdated: "Live from Backend"
      });
    }
  }

  const filteredFlags = allFlags.filter(f => 
    f.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
    f.id.toLowerCase().includes(searchQuery.toLowerCase())
  ).filter((f) => (activeOnly ? f.status : true));

  const handleCreateFlag = () => {
    const nextId = `custom-flag-${Date.now()}`;
    setFlags((prev) => [
      {
        id: nextId,
        name: "New Custom Flag",
        description: "Created from dashboard",
        status: false,
        rollout: 0,
        environment: "Development",
        lastUpdated: "Just now",
      },
      ...prev,
    ]);
  };

  return (
    <div className="flex-1 space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Feature Flags</h1>
          <p className="text-muted-foreground mt-1">Manage and monitor your feature rollouts.</p>
        </div>
        <Button className="rounded-full shadow-md shadow-primary/20 hover:shadow-primary/30 transition-shadow" onClick={handleCreateFlag}>
          <Plus className="mr-2 h-4 w-4" />
          Create Flag
        </Button>
      </div>

      <div className="flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input 
            placeholder="Search flags..." 
            className="pl-9 rounded-full bg-card/50 backdrop-blur-sm border-border/50"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <Button
          variant="outline"
          className="rounded-full border-border/50 bg-card/50 backdrop-blur-sm"
          onClick={() => setActiveOnly((prev) => !prev)}
        >
          <Filter className="mr-2 h-4 w-4" />
          {activeOnly ? "Active Only" : "All Flags"}
        </Button>
      </div>

      <div className="grid gap-4 mt-6">
        {filteredFlags.map((flag) => (
          <Card 
            key={flag.id} 
            className="border-border/50 bg-card/50 backdrop-blur-sm hover:border-primary/30 hover:shadow-md transition-all cursor-pointer group"
            onClick={() => router.push(`/flags/${flag.id}`)}
          >
            <CardContent className="p-0 flex items-center justify-between">
              <div className="p-6 flex items-center gap-6 flex-1">
                <div onClick={(e) => e.stopPropagation()}>
                  <AnimatedToggle 
                    isOn={flag.status} 
                    onToggle={(state) => handleToggle(flag.id, state)} 
                  />
                </div>
                
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h3 className="font-semibold text-lg">{flag.name}</h3>
                    <Badge variant={flag.environment === "Production" ? "default" : "secondary"} className="rounded-full text-xs font-medium">
                      {flag.environment}
                    </Badge>
                    <Badge variant="outline" className="rounded-full text-xs font-medium bg-background/50">
                      {flag.rollout}% Rollout
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">{flag.description}</p>
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
      </div>
    </div>
  );
}
