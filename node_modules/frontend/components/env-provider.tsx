"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { api, DashboardData, State } from "@/lib/api";

interface EnvContextType {
  dashboard: DashboardData | null;
  state: State | null;
  connectionState: "connected" | "disconnected" | "checking";
  connectionText: string;
  isSimulating: boolean;
  setIsSimulating: (val: boolean) => void;
  runSimulationStep: () => Promise<void>;
  fetchData: () => Promise<void>;
}

const EnvContext = createContext<EnvContextType | undefined>(undefined);

export const EnvProvider = ({ children }: { children: ReactNode }) => {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [state, setState] = useState<State | null>(null);
  const [connectionState, setConnectionState] = useState<"connected" | "disconnected" | "checking">("checking");
  const [connectionText, setConnectionText] = useState("Checking Connection...");
  const [isSimulating, setIsSimulating] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [dashData, stateData] = await Promise.all([
        api.getDashboard(),
        api.getState(),
      ]);
      setDashboard(dashData);
      setState(stateData);
      setConnectionState("connected");
      setConnectionText("Connected");
    } catch (error) {
      console.error("Failed to fetch data:", error);
      setConnectionState("disconnected");
      setConnectionText("Disconnected");
    }
  }, []);

  const runSimulationStep = useCallback(async () => {
    if (!state) return;
    try {
      // Very simple simulation: just a "Maintain" action to keep the loop going
      await api.step({
        action_type: "MAINTAIN",
        target_percentage: state.history[state.history.length - 1]?.observation?.current_rollout_percentage ?? 0,
        reason: "Autonomous simulation step",
      });
      await fetchData();
    } catch (error) {
      console.error("Simulation step failed:", error);
      setIsSimulating(false);
    }
  }, [state, fetchData]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <EnvContext.Provider
      value={{
        dashboard,
        state,
        connectionState,
        connectionText,
        isSimulating,
        setIsSimulating,
        runSimulationStep,
        fetchData,
      }}
    >
      {children}
    </EnvContext.Provider>
  );
};

export const useEnv = () => {
  const context = useContext(EnvContext);
  if (context === undefined) {
    throw new Error("useEnv must be used within an EnvProvider");
  }
  return context;
};
