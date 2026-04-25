"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Flag,
  Beaker,
  BrainCircuit,
  Settings,
} from "lucide-react";
import { motion } from "framer-motion";

const sidebarNavItems = [
  {
    title: "Dashboard",
    href: "/",
    icon: LayoutDashboard,
  },
  {
    title: "Feature Flags",
    href: "/flags",
    icon: Flag,
  },
  {
    title: "Experiments",
    href: "/experiments",
    icon: Beaker,
  },
  {
    title: "AI Decisions",
    href: "/ai-decisions",
    icon: BrainCircuit,
  },
  {
    title: "Settings",
    href: "/settings",
    icon: Settings,
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden md:flex w-64 flex-col border-r bg-card h-full">
      <div className="p-6">
        <Link href="/" className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground font-bold shadow-lg shadow-primary/20">
            F
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-lg leading-none tracking-tight">FeatureFlag</span>
            <span className="text-[10px] text-muted-foreground mt-1 font-medium leading-tight">
              Autonomous Rollout Intelligence <br/> for Production Systems
            </span>
          </div>
        </Link>
      </div>

      <nav className="flex-1 space-y-1 px-4 py-2">
        {sidebarNavItems.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "text-primary"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              {isActive && (
                <motion.div
                  layoutId="sidebar-active-indicator"
                  className="absolute inset-0 rounded-lg bg-primary/10"
                  initial={false}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                />
              )}
              <item.icon className="h-4 w-4 relative z-10" />
              <span className="relative z-10">{item.title}</span>
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t">
        <div className="flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-muted transition-colors cursor-pointer">
          <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center">
            <span className="text-xs font-semibold">SA</span>
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-medium">Soham Admin</span>
            <span className="text-xs text-muted-foreground">soham@example.com</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
