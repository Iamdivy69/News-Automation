import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Play } from "lucide-react";
import { fetchArticles, fetchArticleImage, runPipeline, fetchAnalytics } from "@/lib/api";
import ArticleModal from "@/components/ArticleModal";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";

export default function Feed() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [selectedArticle, setSelectedArticle] = useState<any>(null);
  const queryClient = useQueryClient();

  const { data: articles = [], isLoading } = useQuery({
    queryKey: ["articles", search, statusFilter, categoryFilter],
    queryFn: () => fetchArticles({ search, status: statusFilter, category: categoryFilter }),
    refetchInterval: 60000,
  });

  const { data: analyticsData } = useQuery({
    queryKey: ["analytics"],
    queryFn: fetchAnalytics,
    staleTime: 120000,
  });

  const pipeline = useMutation({
    mutationFn: runPipeline,
    onSuccess: (data) => {
      if (data?.statusCode === 409) {
        toast.warning("Pipeline is already running");
      } else {
        toast.success("Pipeline started successfully");
      }
      queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
    onError: () => toast.error("Failed to connect to API — is Flask running?"),
  });

  const scoreColor = (score: number) =>
    score >= 80 ? "bg-success" : score >= 60 ? "bg-warning" : "bg-destructive";

  return (
    <div className="space-y-6">
      {/* Top bar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search articles..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-border bg-card py-2 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
        >
          <option value="">All Status</option>
          <option value="summarised">Summarised</option>
          <option value="approved">Approved</option>
          <option value="publish_approved">Publish Approved</option>
          <option value="published">Published</option>
          <option value="new">New</option>
          <option value="discarded">Discarded</option>
        </select>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
        >
          <option value="">All Categories</option>
          {(analyticsData?.categories ?? []).map((cat: any) => (
            <option key={cat.name} value={cat.name}>
              {cat.name.charAt(0).toUpperCase() + cat.name.slice(1)}
            </option>
          ))}
        </select>

        <button
          onClick={() => pipeline.mutate()}
          disabled={pipeline.isPending}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-all hover:bg-primary/90 active:scale-[0.97] disabled:opacity-50"
        >
          <Play className="h-4 w-4" />
          {pipeline.isPending ? "Running..." : "Run Pipeline"}
        </button>
      </div>

      {/* Article grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-64 animate-pulse rounded-lg bg-card" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {(Array.isArray(articles) ? articles : []).map((article: any, i: number) => (
            <button
              key={article.id ?? i}
              onClick={() => setSelectedArticle(article)}
              className="group relative overflow-hidden rounded-lg border border-border bg-card text-left transition-all duration-200 hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5 active:scale-[0.98]"
              style={{ animationDelay: `${i * 60}ms` }}
            >
              {article.is_breaking && (
                <div className="bg-destructive px-3 py-1 text-xs font-bold text-destructive-foreground">
                  ⚡ BREAKING NEWS
                </div>
              )}

              <div className="flex gap-4 p-4">
                <img
                  src={fetchArticleImage(article.id)}
                  alt=""
                  className="h-24 w-24 shrink-0 rounded-md object-cover bg-muted"
                  onError={(e) => {
                    e.currentTarget.src = "/placeholder.svg";
                  }}
                />

                <div className="min-w-0 flex-1 space-y-2">
                  <h3 className="line-clamp-2 text-sm font-semibold leading-snug text-foreground">
                    {article.headline}
                  </h3>

                  <div className="flex flex-wrap items-center gap-1.5">
                    {article.source && (
                      <span className="platform-badge bg-secondary text-secondary-foreground text-[10px]">
                        {article.source}
                      </span>
                    )}
                    {article.category && (
                      <span className="platform-badge bg-primary/15 text-primary text-[10px]">
                        {article.category}
                      </span>
                    )}
                  </div>

                  {/* Score bar */}
                  {article.viral_score != null && (
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] text-muted-foreground">Viral Score</span>
                        <span className="text-[10px] font-medium text-foreground">{article.viral_score}</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                        <div
                          className={`h-full rounded-full transition-all ${scoreColor(article.viral_score)}`}
                          style={{ width: `${Math.min(article.viral_score, 100)}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {article.created_at && (
                    <p className="text-[10px] text-muted-foreground">
                      {formatDistanceToNow(new Date(article.created_at), { addSuffix: true })}
                    </p>
                  )}
                </div>
              </div>
            </button>
          ))}

          {!isLoading && Array.isArray(articles) && articles.length === 0 && (
            <div className="col-span-2 flex flex-col items-center justify-center py-24 text-center">
              <p className="text-base font-semibold text-foreground">No articles found</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {statusFilter || search || categoryFilter
                  ? "Try clearing your filters"
                  : "Run the pipeline to discover and process articles"}
              </p>
              <button
                onClick={() => pipeline.mutate()}
                disabled={pipeline.isPending}
                className="mt-4 flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                <Play className="h-4 w-4" />
                {pipeline.isPending ? "Running..." : "Run Pipeline Now"}
              </button>
            </div>
          )}
        </div>
      )}

      {selectedArticle && (
        <ArticleModal article={selectedArticle} onClose={() => setSelectedArticle(null)} />
      )}
    </div>
  );
}
