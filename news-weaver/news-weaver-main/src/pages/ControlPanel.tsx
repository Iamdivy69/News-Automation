import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchPipelineStatus, runPipeline, fetchPipelineHistory,
  fetchPendingApproval, fetchQueuedPosts, approvePost, rejectPost, clearQueue,
} from "@/lib/api";
import { Play, CheckCircle, XCircle, Clock, Zap, Trash2 } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";

export default function ControlPanel() {
  const queryClient = useQueryClient();

  const { data: status } = useQuery({
    queryKey: ["pipelineStatus"],
    queryFn: fetchPipelineStatus,
    refetchInterval: 10000,
  });

  const { data: history = [] } = useQuery({
    queryKey: ["pipelineHistory"],
    queryFn: fetchPipelineHistory,
    refetchInterval: 30000,
  });

  const { data: pendingArticles = [] } = useQuery({
    queryKey: ["pendingApproval"],
    queryFn: fetchPendingApproval,
    refetchInterval: 30000,
  });

  const { data: queuedArticles = [] } = useQuery({
    queryKey: ["queuedPosts"],
    queryFn: fetchQueuedPosts,
    refetchInterval: 30000,
  });

  const [activeTab, setActiveTab] = useState<"approval" | "queued">("approval");

  const pipelineMutation = useMutation({
    mutationFn: runPipeline,
    onSuccess: (data) => {
      if (data?.statusCode === 409) {
        toast.warning("Pipeline is already running");
      } else {
        toast.success("Pipeline started — check status above");
      }
      queryClient.invalidateQueries({ queryKey: ["pipelineStatus"] });
      queryClient.invalidateQueries({ queryKey: ["pipelineHistory"] });
    },
    onError: () => toast.error("Failed to start pipeline"),
  });

  const approveMutation = useMutation({
    mutationFn: (id: string | number) => approvePost(id),
    onSuccess: () => {
      toast.success("Article approved for publishing");
      queryClient.invalidateQueries({ queryKey: ["pendingApproval"] });
    },
    onError: () => toast.error("Approve failed"),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string | number) => rejectPost(id),
    onSuccess: () => {
      toast.warning("Article rejected");
      queryClient.invalidateQueries({ queryKey: ["pendingApproval"] });
    },
    onError: () => toast.error("Reject failed"),
  });

  const clearQueueMutation = useMutation({
    mutationFn: clearQueue,
    onSuccess: (data) => {
      toast.success(`Cleared ${data?.count ?? 0} articles from the queue`);
      queryClient.invalidateQueries({ queryKey: ["queuedPosts"] });
    },
    onError: () => toast.error("Failed to clear queue"),
  });

  const lastRun = status?.last_run ?? {};

  return (
    <div className="space-y-6">
      {/* Pipeline control */}
      <div className="rounded-lg border border-border bg-card p-6">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Zap className="h-5 w-5 text-primary" />
            <h3 className="text-lg font-semibold text-foreground">Pipeline Control</h3>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`status-dot ${
                status?.is_running ? "status-dot-running"
                : status?.status === "offline" ? "status-dot-error"
                : "status-dot-idle"
              }`}
            />
            <span className="text-sm capitalize text-muted-foreground">
              {status?.is_running ? "Running" : status?.status === "offline" ? "Offline" : "Idle"}
            </span>
          </div>
        </div>

        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-5">
          {[
            { label: "Discovered", value: lastRun.discovered },
            { label: "Scored", value: lastRun.scored },
            { label: "Summarised", value: lastRun.summarised },
            { label: "Published", value: lastRun.published },
            { label: "Images", value: lastRun.images_generated },
          ].map((m) => (
            <div key={m.label} className="rounded-md bg-muted p-3 text-center">
              <p className="text-lg font-bold text-foreground">{m.value ?? "—"}</p>
              <p className="text-xs text-muted-foreground">{m.label}</p>
            </div>
          ))}
        </div>

        <button
          onClick={() => pipelineMutation.mutate()}
          disabled={pipelineMutation.isPending || status?.is_running === true}
          className="flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-all hover:bg-primary/90 active:scale-[0.97] disabled:opacity-50"
        >
          <Play className="h-4 w-4" />
          {pipelineMutation.isPending ? "Starting..." : "Run Now"}
        </button>
      </div>

      {/* Queues Section */}
      <div className="rounded-lg border border-border bg-card p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-foreground">Content Queues</h3>
          <div className="flex gap-2 items-center">
            <button
              onClick={() => setActiveTab("approval")}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                activeTab === "approval" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground"
              }`}
            >
              Needs Approval ({(Array.isArray(pendingArticles) ? pendingArticles : []).length})
            </button>
            <button
              onClick={() => setActiveTab("queued")}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                activeTab === "queued" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground"
              }`}
            >
              Publishing Queue ({(Array.isArray(queuedArticles) ? queuedArticles : []).length})
            </button>
            {activeTab === "queued" && (Array.isArray(queuedArticles) ? queuedArticles : []).length > 0 && (
              <button
                onClick={() => clearQueueMutation.mutate()}
                disabled={clearQueueMutation.isPending}
                className="flex items-center gap-1.5 rounded-md bg-destructive/15 px-3 py-1.5 text-sm font-medium text-destructive transition-colors hover:bg-destructive/25 active:scale-95 disabled:opacity-50"
                title="Clear all queued articles"
              >
                <Trash2 className="h-3.5 w-3.5" />
                {clearQueueMutation.isPending ? "Clearing..." : "Clear Queue"}
              </button>
            )}
          </div>
        </div>

        <div className="space-y-3">
          {activeTab === "approval" ? (
            // Approval Queue List
            <>
              {(Array.isArray(pendingArticles) ? pendingArticles : []).map((article: any) => (
                <div key={article.id} className="flex items-center justify-between rounded-lg bg-muted/50 p-4">
                  <div className="flex items-center gap-4 w-full">
                    <img
                      src={`/api/articles/${article.id}/image`}
                      alt=""
                      className="h-16 w-24 shrink-0 rounded-md object-cover bg-muted"
                      onError={(e) => { e.currentTarget.style.display = 'none'; }}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-foreground">{article.headline}</p>
                      <div className="mt-1 flex items-center gap-2">
                        {article.source && <span className="text-xs text-muted-foreground">{article.source}</span>}
                        {article.viral_score != null && <span className="text-xs text-primary">Score: {article.viral_score}</span>}
                      </div>
                    </div>
                    <div className="flex shrink-0 gap-2">
                      <button onClick={() => approveMutation.mutate(article.id)} className="rounded-md bg-success/15 p-2 text-success transition-colors hover:bg-success/25 active:scale-95" title="Approve">
                        <CheckCircle className="h-4 w-4" />
                      </button>
                      <button onClick={() => rejectMutation.mutate(article.id)} className="rounded-md bg-destructive/15 p-2 text-destructive transition-colors hover:bg-destructive/25 active:scale-95" title="Reject">
                        <XCircle className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
              {(Array.isArray(pendingArticles) ? pendingArticles : []).length === 0 && (
                <p className="py-4 text-center text-sm text-muted-foreground">No articles pending approval</p>
              )}
            </>
          ) : (
            // Publishing Queue List
            <>
              {(Array.isArray(queuedArticles) ? queuedArticles : []).map((article: any) => (
                <div key={article.id} className="flex items-center justify-between rounded-lg bg-muted/50 p-4">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">{article.headline}</p>
                    <div className="mt-1 flex items-center gap-2">
                      {article.source && <span className="text-xs text-muted-foreground">{article.source}</span>}
                      <span className="text-xs text-primary">Publishing next cycle</span>
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <button onClick={() => rejectMutation.mutate(article.id)} className="rounded-md bg-destructive/15 p-2 text-destructive transition-colors hover:bg-destructive/25 active:scale-95" title="Cancel & Reject">
                      <XCircle className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
              {(Array.isArray(queuedArticles) ? queuedArticles : []).length === 0 && (
                <p className="py-4 text-center text-sm text-muted-foreground">Publishing queue is empty</p>
              )}
            </>
          )}
        </div>
      </div>

      {/* Pipeline history */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h3 className="mb-4 text-lg font-semibold text-foreground">Pipeline History</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="px-3 py-2 text-xs font-medium text-muted-foreground">Time</th>
                <th className="px-3 py-2 text-xs font-medium text-muted-foreground">Status</th>
                <th className="px-3 py-2 text-xs font-medium text-muted-foreground">Discovered</th>
                <th className="px-3 py-2 text-xs font-medium text-muted-foreground">Published</th>
                <th className="px-3 py-2 text-xs font-medium text-muted-foreground">Duration</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(Array.isArray(history) ? history : []).slice(0, 10).map((run: any, i: number) => (
                <tr key={i} className="hover:bg-muted/20">
                  <td className="px-3 py-2 text-muted-foreground">
                    {run.started_at
                      ? formatDistanceToNow(new Date(run.started_at), { addSuffix: true })
                      : "—"}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`platform-badge ${
                        run.status === "completed"
                          ? "bg-success/15 text-success"
                          : run.status === "failed"
                          ? "bg-destructive/15 text-destructive"
                          : "bg-warning/15 text-warning"
                      }`}
                    >
                      {run.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-foreground">{run.discovered ?? "—"}</td>
                  <td className="px-3 py-2 text-foreground">{run.published ?? "—"}</td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {run.duration ?? "—"}
                  </td>
                </tr>
              ))}
              {(Array.isArray(history) ? history : []).length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">
                    No pipeline runs yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
