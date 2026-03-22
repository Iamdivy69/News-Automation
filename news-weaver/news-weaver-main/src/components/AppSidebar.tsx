import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Newspaper, BarChart3, Share2, Settings, Activity,
  ChevronLeft, ChevronRight, Zap,
} from "lucide-react";
import { fetchPipelineStatus } from "@/lib/api";

const navItems = [
  { label: "Feed", path: "/", icon: Newspaper },
  { label: "Analytics", path: "/analytics", icon: BarChart3 },
  { label: "Platform Tracker", path: "/platforms", icon: Share2 },
  { label: "Control Panel", path: "/control", icon: Settings },
  { label: "System Health", path: "/health", icon: Activity },
];

export default function AppSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  const { data: pipelineStatus } = useQuery({
    queryKey: ["pipelineStatus"],
    queryFn: fetchPipelineStatus,
    refetchInterval: 10000,
  });

  // Derive a simple status string from the API shape
  const isRunning = pipelineStatus?.is_running;
  const isOffline = pipelineStatus?.status === "offline";
  const statusLabel = isRunning ? "Running" : isOffline ? "Offline" : "Idle";
  const dotClass = isRunning
    ? "status-dot-running"
    : isOffline
    ? "status-dot-error"
    : "status-dot-idle";

  return (
    <aside
      className={`flex flex-col border-r border-border bg-sidebar transition-all duration-300 ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 border-b border-border px-4">
        <Zap className="h-6 w-6 shrink-0 text-primary" />
        {!collapsed && (
          <span className="text-sm font-bold tracking-tight text-foreground">
            Synthetix News
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 p-2">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors duration-150 ${
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              }`}
            >
              <item.icon className="h-4.5 w-4.5 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Pipeline status */}
      <div className="border-t border-border p-3">
        <div className="flex items-center gap-2">
          <span className={`status-dot ${dotClass}`} />
          {!collapsed && (
            <span className="text-xs text-muted-foreground">
              Pipeline {statusLabel}
            </span>
          )}
        </div>
      </div>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex h-10 items-center justify-center border-t border-border text-muted-foreground transition-colors hover:text-foreground"
      >
        {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
      </button>
    </aside>
  );
}
