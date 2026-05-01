import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity, BarChart3, Cpu, LayoutDashboard,
  Share2, ChevronLeft, ChevronRight, Zap,
} from "lucide-react";
import { fetchPipelineStatus } from "@/lib/api";

const navItems = [
  { label: "Pipeline Monitor", path: "/",               icon: LayoutDashboard },
  { label: "Top 30 Content",   path: "/feed",           icon: Cpu },
  { label: "Platform Posts",   path: "/platform-tracker", icon: Share2 },
  { label: "Analytics",        path: "/analytics",      icon: BarChart3 },
  { label: "System Health",    path: "/health",         icon: Activity },
];

export default function AppSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  const { data: pipelineStatus } = useQuery({
    queryKey: ["pipelineStatus"],
    queryFn: fetchPipelineStatus,
    refetchInterval: 10000,
  });

  const isRunning = pipelineStatus?.is_running;
  const isOffline = pipelineStatus?.status === "offline";
  const statusLabel = isRunning ? "Running" : isOffline ? "Offline" : "Idle";

  return (
    <aside
      className={`flex flex-col border-r border-border bg-sidebar transition-all duration-300 ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 border-b border-border px-4">
        <Zap className="h-5 w-5 shrink-0 text-primary" />
        {!collapsed && (
          <span className="text-sm font-black tracking-tight text-foreground">
            Synthetix News
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 p-2 pt-3">
        {navItems.map((item) => {
          const isActive =
            item.path === "/"
              ? location.pathname === "/"
              : location.pathname.startsWith(item.path);
          const isPipelineMonitor = item.path === "/";

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
              <item.icon className="h-4 w-4 shrink-0" />
              {!collapsed && (
                <span className="flex-1 truncate">{item.label}</span>
              )}
              {/* Pulsing dot on Pipeline Monitor when running */}
              {!collapsed && isPipelineMonitor && isRunning && (
                <span className="relative flex h-2 w-2 shrink-0">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Pipeline status footer */}
      <div className="border-t border-border p-3">
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full shrink-0 ${
              isRunning
                ? "bg-green-500 animate-pulse"
                : isOffline
                ? "bg-red-500"
                : "bg-muted-foreground/30"
            }`}
          />
          {!collapsed && (
            <span className="text-xs text-muted-foreground truncate">
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
        {collapsed ? (
          <ChevronRight className="h-4 w-4" />
        ) : (
          <ChevronLeft className="h-4 w-4" />
        )}
      </button>
    </aside>
  );
}
