import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchTrackerStats, fetchPosts, fetchArticleImage } from "@/lib/api";
import { Send, Clock, CheckCircle, XCircle } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

const platforms = ["all", "telegram", "twitter", "linkedin", "instagram"] as const;

const platformColors: Record<string, string> = {
  telegram: "bg-telegram/15 text-telegram",
  twitter: "bg-twitter/15 text-twitter",
  linkedin: "bg-linkedin/15 text-linkedin",
  instagram: "bg-instagram/15 text-instagram",
};

export default function PlatformTracker() {
  const [activePlatform, setActivePlatform] = useState("all");
  const [selectedPost, setSelectedPost] = useState<any>(null);

  const { data: stats } = useQuery({
    queryKey: ["trackerStats"],
    queryFn: fetchTrackerStats,
    refetchInterval: 30000,
  });

  const { data: posts = [] } = useQuery({
    queryKey: ["posts", activePlatform],
    queryFn: () => fetchPosts(activePlatform === "all" ? undefined : activePlatform),
    refetchInterval: 30000,
  });

  const statCards = [
    { label: "Total Posted", value: stats?.total_posted ?? "—", icon: Send },
    { label: "Posted Today", value: stats?.posted_today ?? "—", icon: CheckCircle },
    { label: "Success Rate", value: stats?.success_rate != null ? `${stats.success_rate}%` : "—", icon: CheckCircle },
    {
      label: "Last Post",
      value: stats?.last_post_time
        ? formatDistanceToNow(new Date(stats.last_post_time), { addSuffix: true })
        : "Never",
      icon: Clock,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {statCards.map((s, i) => (
          <div
            key={s.label}
            className="metric-card opacity-0 animate-fade-up"
            style={{ animationDelay: `${i * 80}ms`, animationFillMode: "forwards" }}
          >
            <s.icon className="mb-2 h-4 w-4 text-primary" />
            <p className="text-2xl font-bold text-foreground">{s.value}</p>
            <p className="text-xs text-muted-foreground">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Platform tabs */}
      <div className="flex gap-1 rounded-lg bg-muted p-1">
        {platforms.map((p) => (
          <button
            key={p}
            onClick={() => setActivePlatform(p)}
            className={`flex-1 rounded-md px-3 py-2 text-sm font-medium capitalize transition-colors ${
              activePlatform === p
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {p}
          </button>
        ))}
      </div>

      {/* Posts table */}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-left text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-xs font-medium text-muted-foreground">Thumbnail</th>
              <th className="px-4 py-3 text-xs font-medium text-muted-foreground">Headline</th>
              <th className="px-4 py-3 text-xs font-medium text-muted-foreground">Platform</th>
              <th className="px-4 py-3 text-xs font-medium text-muted-foreground">Posted</th>
              <th className="px-4 py-3 text-xs font-medium text-muted-foreground">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {(Array.isArray(posts) ? posts : []).map((post: any, i: number) => (
              <tr
                key={post.id ?? i}
                onClick={() => setSelectedPost(post)}
                className="cursor-pointer bg-card transition-colors hover:bg-muted/30"
              >
                <td className="px-4 py-3">
                  <img
                    src={fetchArticleImage(post.article_id)}
                    alt=""
                    style={{ width: 64, height: 40, objectFit: "cover", borderRadius: 4 }}
                    onError={(e) => {
                      e.currentTarget.style.display = "none";
                      const placeholder = e.currentTarget.nextElementSibling as HTMLElement;
                      if (placeholder) placeholder.style.display = "block";
                    }}
                  />
                  <div
                    className="h-10 w-16 rounded bg-muted"
                    style={{ display: "none" }}
                  />
                </td>
                <td className="max-w-[250px] truncate px-4 py-3 text-foreground">
                  {post.headline?.slice(0, 60) ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <span className={`platform-badge ${platformColors[post.platform] ?? "bg-secondary text-secondary-foreground"}`}>
                    {post.platform}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {post.posted_at
                    ? formatDistanceToNow(new Date(post.posted_at), { addSuffix: true })
                    : "—"}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`platform-badge ${
                      post.status === "published"
                        ? "bg-success/15 text-success"
                        : "bg-destructive/15 text-destructive"
                    }`}
                  >
                    {post.status}
                  </span>
                </td>
              </tr>
            ))}
            {(Array.isArray(posts) ? posts : []).length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                  No posts found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Slide-over panel */}
      {selectedPost && (
        <div className="fixed inset-0 z-50 flex justify-end bg-background/60 backdrop-blur-sm" onClick={() => setSelectedPost(null)}>
          <div
            className="w-full max-w-md border-l border-border bg-card p-6 shadow-2xl animate-slide-in-right overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-6 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-foreground">Post Details</h3>
              <button onClick={() => setSelectedPost(null)} className="text-muted-foreground hover:text-foreground">
                <XCircle className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <p className="text-xs text-muted-foreground">Headline</p>
                <p className="text-sm font-medium text-foreground">{selectedPost.headline}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Platform</p>
                <span className={`platform-badge ${platformColors[selectedPost.platform] ?? "bg-secondary text-secondary-foreground"}`}>
                  {selectedPost.platform}
                </span>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Caption</p>
                <div className="mt-1 rounded-lg bg-muted p-3 text-sm text-foreground whitespace-pre-wrap">
                  {selectedPost.caption ?? selectedPost.content ?? "No caption available"}
                </div>
              </div>
              {selectedPost.image_url && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Image</p>
                  <img src={selectedPost.image_url} alt="" className="rounded-lg w-full" />
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
