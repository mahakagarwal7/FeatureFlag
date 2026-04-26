"use client";

import { Bell, Search, Globe, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ThemeToggle } from "@/components/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { useEnv } from "@/components/env/env-provider";

export function Navbar() {
  const { state } = useEnv();

  const lastObs = state?.history?.[state.history.length - 1]?.observation;
  const tenantId = String(
    (lastObs?.extra_context as Record<string, unknown> | undefined)?.tenant_id ?? "Global"
  );

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b bg-background/80 px-6 backdrop-blur-sm">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <Badge variant="outline" className="rounded-full bg-indigo-50 text-indigo-700 border-indigo-200 gap-1 px-3">
             <Globe className="h-3 w-3" />
             {state?.scenario_name || "Production"}
          </Badge>
          <Badge variant="outline" className="rounded-full bg-amber-50 text-amber-700 border-amber-200 gap-1 px-3">
             <Shield className="h-3 w-3" />
             Tenant: {tenantId}
          </Badge>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="relative hidden lg:flex items-center">
          <Search className="absolute left-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search flags, incidents..."
            className="w-64 rounded-full bg-muted/50 pl-9 border-none focus-visible:ring-1"
          />
        </div>

        <Button variant="ghost" size="icon" className="relative rounded-full">
          <Bell className="h-5 w-5" />
          {lastObs?.chaos_incident && (
            <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-destructive animate-ping" />
          )}
        </Button>
        <ThemeToggle />
      </div>
    </header>
  );
}
