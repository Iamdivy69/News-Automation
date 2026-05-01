import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from '@/components/ui/table';
import {
  Database, Brain, Sparkles, Image, Cloud, Zap,
  CheckCircle2, XCircle, MinusCircle, RefreshCw,
  BarChart3, Clock, TrendingUp, Newspaper,
} from 'lucide-react';
import { fetchHealth, fetchPipelineLogs, fetchPipelineStatus, relativeTime, formatDurationSec } from '@/lib/api';

// ── Types ─────────────────────────────────────────────────────────────────────
type ServiceStatus = 'connected' | 'healthy' | 'error' | 'disabled' | 'unknown';

type ServiceInfo = {
  key: string;
  label: string;
  Icon: React.ElementType;
  status: ServiceStatus;
  detail: string;
};

// ── Status badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: ServiceStatus }) {
  const cfg: Record<ServiceStatus, { cls: string; label: string; Icon: React.ElementType }> = {
    connected: { cls: 'bg-green-500/15 text-green-700 border-green-500/30', label: 'Connected', Icon: CheckCircle2 },
    healthy:   { cls: 'bg-green-500/15 text-green-700 border-green-500/30', label: 'Healthy',   Icon: CheckCircle2 },
    error:     { cls: 'bg-red-500/15 text-red-700 border-red-500/30',       label: 'Error',     Icon: XCircle },
    disabled:  { cls: 'bg-muted text-muted-foreground border-border',       label: 'Disabled',  Icon: MinusCircle },
    unknown:   { cls: 'bg-yellow-500/15 text-yellow-700 border-yellow-500/30', label: 'Checking…', Icon: RefreshCw },
  };
  const { cls, label, Icon } = cfg[status];
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded border ${cls}`}>
      <Icon className="w-3 h-3" />
      {label}
    </span>
  );
}

// ── Service card ──────────────────────────────────────────────────────────────
function ServiceCard({ label, Icon, status, detail }: ServiceInfo) {
  const borderCls =
    status === 'error'   ? 'border-red-400' :
    status === 'disabled'? 'border-muted'   : 'border-border';

  return (
    <Card className={`shadow-sm ${borderCls}`}>
      <CardContent className="p-4 flex items-start gap-3">
        <div className={`mt-0.5 rounded-md p-2 ${
          status === 'error' ? 'bg-red-100 text-red-600' :
          status === 'disabled' ? 'bg-muted text-muted-foreground' :
          'bg-primary/10 text-primary'
        }`}>
          <Icon className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-sm">{label}</span>
            <StatusBadge status={status} />
          </div>
          <p className="text-xs text-muted-foreground mt-0.5 truncate">{detail}</p>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Stat metric card ──────────────────────────────────────────────────────────
function MetricCard({ label, value, Icon, color }: {
  label: string; value: string | number; Icon: React.ElementType; color: string;
}) {
  return (
    <Card className="shadow-sm">
      <CardContent className="p-4 flex items-center gap-3">
        <div className={`rounded-md p-2 ${color}`}>
          <Icon className="w-4 h-4" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground font-medium">{label}</p>
          <p className="text-2xl font-black tabular-nums">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function Health() {
  const [health, setHealth]   = useState<any>(null);
  const [logs, setLogs]       = useState<any[]>([]);
  const [pipeline, setPipeline] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [h, l, p] = await Promise.allSettled([
        fetchHealth(),
        fetchPipelineLogs(),
        fetchPipelineStatus(),
      ]);
      if (h.status === 'fulfilled') setHealth(h.value);
      if (l.status === 'fulfilled') setLogs(Array.isArray(l.value) ? l.value : []);
      if (p.status === 'fulfilled') setPipeline(p.value);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 30000);
    return () => clearInterval(iv);
  }, [load]);

  // Build per-stage latest row from logs
  const stageLatest: Record<string, any> = {};
  logs.forEach(r => {
    if (!stageLatest[r.stage] || new Date(r.started_at) > new Date(stageLatest[r.stage].started_at)) {
      stageLatest[r.stage] = r;
    }
  });

  const services: ServiceInfo[] = health ? [
    {
      key: 'postgresql', label: 'PostgreSQL', Icon: Database,
      status: health.postgresql?.status === 'connected' ? 'connected' : 'error',
      detail: health.postgresql?.details ?? 'Checking…',
    },
    {
      key: 'ollama', label: 'Ollama (Mistral)', Icon: Brain,
      status: health.ollama?.status === 'healthy' ? 'healthy' : 'error',
      detail: health.ollama?.details ?? 'Offline',
    },
    {
      key: 'gemini', label: 'Gemini API', Icon: Sparkles,
      status: health.gemini?.status === 'healthy' ? 'healthy' : 'error',
      detail: health.gemini?.details ?? 'Not configured',
    },
    {
      key: 'pexels', label: 'Pexels (Fallback)', Icon: Image,
      status: (health.pexels?.status === 'healthy' ? 'healthy' : health.pexels?.status === 'disabled' ? 'disabled' : 'error') as ServiceStatus,
      detail: health.pexels?.status === 'disabled' ? 'Fallback only — primary is Gemini' : health.pexels?.details ?? 'Not configured',
    },
    {
      key: 'cloudinary', label: 'Cloudinary CDN', Icon: Cloud,
      status: (health.cloudinary?.status === 'healthy' ? 'healthy' : 'disabled') as ServiceStatus,
      detail: health.cloudinary?.details ?? 'Not configured',
    },
    {
      key: 'pipeline', label: 'Pipeline Engine', Icon: Zap,
      status: (pipeline?.is_running ? 'healthy' : pipeline?.status === 'offline' ? 'error' : 'healthy') as ServiceStatus,
      detail: pipeline?.last_run
        ? `Last run ${relativeTime(pipeline.last_run)}`
        : 'No runs recorded',
    },
  ] : [];

  const STAGES = ['discovery', 'viral_score', 'dedup', 'top30_selector', 'summarisation', 'image_generation', 'publishing'];

  return (
    <div className="p-6 lg:p-8 max-w-screen-2xl mx-auto space-y-8 animate-in fade-in duration-500">

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-black tracking-tight">System Health</h1>
        <button
          onClick={load}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Service grid */}
      <section>
        <h2 className="text-sm font-bold uppercase tracking-widest text-muted-foreground mb-3">
          Services
        </h2>
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Card key={i}><CardContent className="p-4"><Skeleton className="h-12 w-full" /></CardContent></Card>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {services.map(s => <ServiceCard key={s.key} {...s} />)}
          </div>
        )}
      </section>

      {/* System metrics */}
      <section>
        <h2 className="text-sm font-bold uppercase tracking-widest text-muted-foreground mb-3">
          System Metrics
        </h2>
        {loading ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Card key={i}><CardContent className="p-4"><Skeleton className="h-10 w-full" /></CardContent></Card>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard
              label="Total Articles in DB"
              value={health?.metrics?.total_articles ?? '—'}
              Icon={Newspaper}
              color="bg-blue-500/10 text-blue-600"
            />
            <MetricCard
              label="Published Today"
              value={health?.metrics?.published_today ?? '—'}
              Icon={CheckCircle2}
              color="bg-green-500/10 text-green-600"
            />
            <MetricCard
              label="Avg Viral Score"
              value={health?.metrics?.avg_viral_score != null
                ? Math.round(health.metrics.avg_viral_score)
                : '—'}
              Icon={TrendingUp}
              color="bg-orange-500/10 text-orange-600"
            />
            <MetricCard
              label="Top-30 Rate"
              value={health?.metrics?.top30_rate != null
                ? `${Math.round(health.metrics.top30_rate)}%`
                : '—'}
              Icon={BarChart3}
              color="bg-purple-500/10 text-purple-600"
            />
          </div>
        )}
      </section>

      {/* Pipeline stage health */}
      <section>
        <h2 className="text-sm font-bold uppercase tracking-widest text-muted-foreground mb-3">
          Pipeline Stage Health
        </h2>
        <Card className="shadow-sm">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="pl-6">Stage</TableHead>
                  <TableHead>Last Run</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead className="text-right">Processed</TableHead>
                  <TableHead className="text-right pr-6">Errors</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 5 }).map((_, j) => (
                        <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                ) : Object.keys(stageLatest).length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8 text-muted-foreground text-sm">
                      No pipeline runs recorded yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  Object.entries(stageLatest).map(([stage, row]) => {
                    const start  = new Date(row.started_at);
                    const end    = row.completed_at ? new Date(row.completed_at) : null;
                    const durSec = end ? (end.getTime() - start.getTime()) / 1000 : null;
                    const hasErr = Number(row.errors) > 0;
                    return (
                      <TableRow key={stage} className="text-sm">
                        <TableCell className="pl-6 font-medium capitalize">{stage.replace(/_/g, ' ')}</TableCell>
                        <TableCell className="text-muted-foreground">{relativeTime(row.started_at)}</TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">
                          {formatDurationSec(durSec)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{row.articles_out ?? '—'}</TableCell>
                        <TableCell className={`text-right pr-6 font-semibold ${hasErr ? 'text-red-600' : 'text-muted-foreground/50'}`}>
                          {hasErr ? row.errors : '—'}
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
