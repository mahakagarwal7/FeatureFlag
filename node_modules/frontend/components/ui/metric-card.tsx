"use client";

import { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  title: string;
  value: string | number;
  icon?: ReactNode;
  trend?: {
    value: number;
    label: string;
    isPositive?: boolean;
  };
  className?: string;
}

export function MetricCard({ title, value, icon, trend, className }: MetricCardProps) {
  return (
    <motion.div
      whileHover={{ y: -2 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      className="h-full"
    >
      <Card className={cn("relative overflow-hidden h-full border-border/50 bg-card/50 backdrop-blur-sm transition-all hover:border-primary/30 hover:shadow-md hover:shadow-primary/5", className)}>
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            {icon && <div className="text-muted-foreground/60">{icon}</div>}
          </div>
          
          <div className="mt-4 flex items-baseline gap-2">
            <h2 className="text-3xl font-bold tracking-tight">{value}</h2>
            
            {trend && (
              <span
                className={cn(
                  "text-xs font-medium px-2 py-1 rounded-full",
                  trend.isPositive === true
                    ? "bg-green-500/10 text-green-500"
                    : trend.isPositive === false
                    ? "bg-red-500/10 text-red-500"
                    : "bg-muted text-muted-foreground"
                )}
              >
                {trend.isPositive ? "+" : ""}
                {trend.value}%
              </span>
            )}
          </div>
          
          {trend && trend.label && (
            <p className="mt-1 text-xs text-muted-foreground">
              {trend.label}
            </p>
          )}
        </CardContent>
        
        {/* Subtle bottom accent line */}
        <div className="absolute bottom-0 left-0 h-[2px] w-full bg-gradient-to-r from-transparent via-primary/10 to-transparent" />
      </Card>
    </motion.div>
  );
}
