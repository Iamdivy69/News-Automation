import { useQuery } from "@tanstack/react-query";
import { fetchAnalytics, fetchInsights } from "@/lib/api";
import { TrendingUp, FileText, Zap, Clock, BarChart3, Lightbulb } from "lucide-react";

export default function Analytics() {
  const { data: analytics, isLoading } = useQuery({
    queryKey: ["analytics"],
    queryFn: fetchAnalytics,
    refetchInterval: 120000,
  });

  const { data: insights } = useQuery({
    queryKey: ["insights"],
    queryFn: fetchInsights,
    refetchInterval: 120000,
  });

  const metrics = [
    { label: "Total Articles", value: analytics?.total_articles ?? "—", icon: FileText },
    { label: "Published", value: analytics?.published ?? "—", icon: Zap },
    { label: "Avg Score", value: analytics?.avg_score?.toFixed(1) ?? "—", icon: TrendingUp },
    { label: "Today", value: analytics?.today ?? "—", icon: Clock },
    { label: "Categories", value: analytics?.category_count ?? "—", icon: BarChart3 },
    { label: "Sources", value: analytics?.source_count ?? "—", icon: Lightbulb },
  ];

  const categories = analytics?.categories ?? [];
  const maxCount = Math.max(...categories.map((c: any) => c.count ?? 0), 1);
  const sources = analytics?.top_sources ?? [];
  const statusDist = analytics?.status_distribution ?? [];

  return (
    <div className="space-y-6">
      {/* Metric cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
        {metrics.map((m, i) => (
          <div
            key={m.label}
            className="metric-card opacity-0 animate-fade-up"
            style={{ animationDelay: `${i * 80}ms`, animationFillMode: "forwards" }}
          >
            <m.icon className="mb-2 h-4 w-4 text-primary" />
            <p className="text-2xl font-bold text-foreground">{m.value}</p>
            <p className="text-xs text-muted-foreground">{m.label}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Category bar chart */}
        <div className="rounded-lg border border-border bg-card p-5">
          <h3 className="mb-4 text-sm font-semibold text-foreground">Articles by Category</h3>
          <div className="space-y-3">
            {categories.map((cat: any) => (
              <div key={cat.name} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-foreground capitalize">{cat.name}</span>
                  <span className="text-muted-foreground">{cat.count}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary transition-all duration-500"
                    style={{ width: `${(cat.count / maxCount) * 100}%` }}
                  />
                </div>
              </div>
            ))}
            {categories.length === 0 && (
              <p className="text-sm text-muted-foreground">No data yet</p>
            )}
          </div>
        </div>

        {/* Top sources */}
        <div className="rounded-lg border border-border bg-card p-5">
          <h3 className="mb-4 text-sm font-semibold text-foreground">Top Sources</h3>
          <div className="space-y-2">
            {sources.map((s: any, i: number) => (
              <div
                key={s.name}
                className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-2"
              >
                <span className="text-sm text-foreground">{s.name}</span>
                <span className="text-sm font-medium text-primary">{s.count}</span>
              </div>
            ))}
            {sources.length === 0 && (
              <p className="text-sm text-muted-foreground">No data yet</p>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Status distribution */}
        <div className="rounded-lg border border-border bg-card p-5">
          <h3 className="mb-4 text-sm font-semibold text-foreground">Status Distribution</h3>
          <div className="flex gap-4">
            {statusDist.map((s: any) => (
              <div key={s.status} className="flex-1 rounded-md bg-muted/50 p-3 text-center">
                <p className="text-lg font-bold text-foreground">{s.count}</p>
                <p className="text-xs capitalize text-muted-foreground">{s.status}</p>
              </div>
            ))}
            {statusDist.length === 0 && (
              <p className="text-sm text-muted-foreground">No data yet</p>
            )}
          </div>
        </div>

        {/* AI Insights */}
        <div className="rounded-lg border border-primary/20 bg-card p-5">
          <div className="mb-3 flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">AI Insight Report</h3>
          </div>
          <p className="text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap">
            {insights?.report ?? "No insights available yet. Run the pipeline to generate analysis."}
          </p>
        </div>
      </div>
    </div>
  );
}
