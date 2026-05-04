const BASE = "/api";

async function apiFetch(path: string, options?: RequestInit) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

// ── Articles ─────────────────────────────────────────────────────────────────

export const fetchArticles = async (params?: {
  search?: string;
  status?: string;
  category?: string;
  page?: number;
  per_page?: number;
}) => {
  const qs = new URLSearchParams();
  if (params?.page) qs.set("page", String(params.page));
  qs.set("per_page", String(params?.per_page ?? 20));
  if (params?.status) qs.set("status", params.status);
  if (params?.category) qs.set("category", params.category);
  if (params?.search) qs.set("search", params.search);
  try {
    const data = await apiFetch(`/articles?${qs.toString()}`);
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
};

export const fetchArticle = (id: string | number) =>
  apiFetch(`/articles/${id}`);

export const fetchTop30 = async () => {
  try {
    const data = await apiFetch('/articles/top30');
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
};

export const patchArticle = (id: string | number, data: any) => 
  apiFetch(`/articles/${id}`, { method: 'PATCH', body: JSON.stringify(data) });

export const regenerateImage = (id: string | number) => 
  apiFetch(`/articles/${id}/regenerate-image`, { method: 'POST' });

export const discardArticle = (id: string | number) => 
  apiFetch(`/articles/${id}/discard`, { method: 'POST' });

/** Returns a direct image URL string — use in <img src={...}> */
export const fetchArticleImage = (id: string | number) =>
  `${BASE}/articles/${id}/image`;

// ── Pipeline ──────────────────────────────────────────────────────────────────

export const fetchPipelineStatus = async () => {
  try {
    const data = await apiFetch("/pipeline/status");
    return {
      ...data,
      // pages check status?.status, so normalise is_running → status string
      status: data.is_running ? "running" : "idle",
    };
  } catch {
    return { is_running: false, status: "offline", last_run: null };
  }
};

export const fetchPipelineStages = () => apiFetch('/pipeline/stages');

export const fetchPipelineLogs = async () => {
  try {
    const res = await apiFetch('/pipeline/logs');
    if (res && Array.isArray(res)) return res;
    if (res && Array.isArray(res.pipeline_runs)) return res.pipeline_runs;
    return [];
  } catch {
    return [];
  }
};

export const runStage = (stageName: string) =>
  fetch(`/api/pipeline/run-stage/${stageName}`, { method: 'POST' }).then(r => r.json());

export const runPipeline = async () => {
  const res = await fetch(`${BASE}/pipeline/run`, { method: "POST" });
  const data = await res.json();
  if (!res.ok && res.status !== 409) throw new Error(data?.message ?? "Failed to start pipeline");
  return { ...data, statusCode: res.status };
};

export const fetchPipelineHistory = async () => {
  try {
    const runs = await apiFetch("/pipeline/history");
    if (!Array.isArray(runs)) return [];
    return runs.map((r: any) => ({
      ...r,
      duration: formatDurationSec(r.duration_sec),
      status: "completed",
    }));
  } catch {
    return [];
  }
};

// ── Analytics (composite: /stats + /posts/tracker/stats + score avg) ──────────

export const fetchAnalytics = async () => {
  const [statsRes, trackerRes, articlesRes] = await Promise.allSettled([
    apiFetch("/stats"),
    apiFetch("/posts/tracker/stats"),
    apiFetch("/articles?per_page=100&status=summarised"),
  ]);

  const s = statsRes.status === "fulfilled" ? statsRes.value : {};
  const t = trackerRes.status === "fulfilled" ? trackerRes.value : {};
  const articles: any[] =
    articlesRes.status === "fulfilled" && Array.isArray(articlesRes.value)
      ? articlesRes.value
      : [];

  const avg_score =
    articles.length > 0
      ? articles.reduce((acc: number, a: any) => acc + (a.viral_score ?? 0), 0) /
        articles.length
      : null;

  const categories = Object.entries(s.articles_by_category ?? {}).map(
    ([name, count]) => ({ name, count: count as number })
  );
  const top_sources = Object.entries(s.top_sources ?? {}).map(
    ([name, count]) => ({ name, count: count as number })
  );
  const status_distribution = Object.entries(s.articles_by_status ?? {}).map(
    ([status, count]) => ({ status, count: count as number })
  );

  return {
    total_articles: s.total_articles ?? 0,
    published: t.total_posted ?? 0,
    avg_score,
    today: s.summarised_today ?? 0,
    category_count: categories.length,
    source_count: top_sources.length,
    categories,
    top_sources,
    status_distribution,
  };
};

export const fetchInsights = async () => {
  try {
    return await apiFetch("/insights");
  } catch {
    return { report: null };
  }
};

// ── Posts / Platform Tracker ──────────────────────────────────────────────────

export const fetchTrackerStats = async () => {
  try {
    const data = await apiFetch("/posts/tracker/stats");
    return { ...data, last_post_time: data.last_post_at ?? null };
  } catch {
    return { total_posted: 0, posted_today: 0, success_rate: 0, last_post_time: null };
  }
};

export const fetchPosts = async (platform?: string) => {
  try {
    const all = await apiFetch("/posts/tracker");
    if (!Array.isArray(all)) return [];
    if (!platform) return all;
    return all.filter((p: any) => p.platform === platform);
  } catch {
    return [];
  }
};

export const fetchPendingApproval = async () => {
  try {
    const data = await apiFetch("/posts/pending");
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
};

export const fetchQueuedPosts = async () => {
  try {
    const data = await apiFetch("/posts/queued");
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
};

export const approvePost = async (id: string | number) =>
  apiFetch(`/posts/${id}/approve`, { method: "POST" });

export const rejectPost = async (id: string | number) =>
  apiFetch(`/posts/${id}/reject`, { method: "POST" });

export const clearQueue = async () =>
  apiFetch(`/posts/queue`, { method: "DELETE" });

// ── Health ────────────────────────────────────────────────────────────────────

export const fetchHealth = async () => {
  try {
    const data = await apiFetch("/health");
    return {
      postgresql: {
        status: data.postgresql === "ok" ? "connected" : "error",
        details: data.postgresql === "ok" ? "Connected successfully" : "Connection failed",
      },
      ollama: {
        status: data.ollama === "ok" ? "healthy" : "error",
        details: data.ollama === "ok" ? "Running mistral" : "Offline",
      },
      gemini: {
        status: data.gemini === "ok" ? "healthy" : "error",
        details: data.gemini === "ok" ? "Gemini API ready" : "Offline or invalid key",
      },
      pexels: {
        status: data.pexels === "ok" ? "healthy" : data.pexels === "disabled" ? "disabled" : "error",
        details: data.pexels === "ok"
          ? "Fallback API ready"
          : data.pexels === "disabled"
          ? "Not configured"
          : "Offline",
      },
      cloudinary: {
        status: data.cloudinary === "ok" ? "healthy" : "disabled",
        details: data.cloudinary === "ok" ? "CDN connected" : "Not configured",
      },
      metrics: {
        total_articles:   data.metrics?.total_articles   ?? null,
        published_today:  data.metrics?.published_today  ?? null,
        avg_viral_score:  data.metrics?.avg_viral_score  ?? null,
        top30_rate:       data.metrics?.top30_rate       ?? null,
      },
      timestamp: data.timestamp ?? null,
    };
  } catch {
    return {
      postgresql:  { status: "unknown", details: "Checking..." },
      ollama:      { status: "unknown", details: "Checking..." },
      gemini:      { status: "unknown", details: "Checking..." },
      pexels:      { status: "unknown", details: "Checking..." },
      cloudinary:  { status: "unknown", details: "Checking..." },
      metrics:     { total_articles: null, published_today: null, avg_viral_score: null, top30_rate: null },
      timestamp:   null,
    };
  }
};

/** Alias: same as fetchHealth, used from Health.tsx */
export const fetchStageHealth = fetchHealth;

// ── Helpers ───────────────────────────────────────────────────────────────────

export function formatDurationSec(sec: number | null | undefined): string {
  if (sec == null) return "—";
  const s = Math.round(sec);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}m ${rem}s`;
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "Never";
  const diff = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
