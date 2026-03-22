import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "@/lib/api";
import { Database, Cpu, RefreshCw } from "lucide-react";

export default function Health() {
  const { data: health, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 15000,
  });

  const services = [
    {
      name: "PostgreSQL",
      icon: Database,
      status: health?.postgresql?.status ?? "unknown",
      details: health?.postgresql?.details ?? "Checking...",
    },
    {
      name: "Ollama (LLM)",
      icon: Cpu,
      status: health?.ollama?.status ?? "unknown",
      details: health?.ollama?.details ?? "Checking...",
    },
  ];

  const statusColor = (s: string) =>
    s === "healthy" || s === "connected"
      ? "status-dot-idle"
      : s === "degraded"
      ? "status-dot-running"
      : "status-dot-error";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">System Health</h2>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <RefreshCw className="h-3 w-3" />
          Auto-refreshes every 15s
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {services.map((svc, i) => (
          <div
            key={svc.name}
            className="metric-card opacity-0 animate-fade-up"
            style={{ animationDelay: `${i * 100}ms`, animationFillMode: "forwards" }}
          >
            <div className="flex items-center gap-3">
              <svc.icon className="h-5 w-5 text-primary" />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-foreground">{svc.name}</h3>
                  <span className={`status-dot ${statusColor(svc.status)}`} />
                </div>
                <p className="mt-1 text-xs capitalize text-muted-foreground">{svc.status}</p>
              </div>
            </div>
            <p className="mt-3 text-xs text-muted-foreground">{svc.details}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
