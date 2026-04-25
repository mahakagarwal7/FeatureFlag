"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface AnimatedToggleProps {
  isOn: boolean;
  onToggle: (isOn: boolean) => void;
  className?: string;
  disabled?: boolean;
}

export function AnimatedToggle({ isOn, onToggle, className, disabled }: AnimatedToggleProps) {
  return (
    <div
      className={cn(
        "relative flex h-6 w-11 cursor-pointer items-center rounded-full p-1 transition-colors",
        isOn ? "bg-primary" : "bg-muted-foreground/30",
        disabled && "opacity-50 cursor-not-allowed",
        className
      )}
      onClick={() => {
        if (!disabled) {
          onToggle(!isOn);
        }
      }}
    >
      <motion.div
        className="h-4 w-4 rounded-full bg-white shadow-sm"
        layout
        transition={{
          type: "spring",
          stiffness: 700,
          damping: 30,
        }}
        animate={{
          x: isOn ? 20 : 0,
        }}
      />
    </div>
  );
}
