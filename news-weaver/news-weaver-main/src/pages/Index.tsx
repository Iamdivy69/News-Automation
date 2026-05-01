import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from '@/components/ui/table';
import {
  Play, ArrowRight, Activity, Clock, AlertCircle,
  CheckCircle2, XCircle, Loader2, RefreshCw,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  fetchPipelineStages,
  fetchPipelineLogs,
  fetchPipelineStatus,
  runPipeline,
  relativeTime,
  formatDurationSec,
} from '@/lib/api';

// ── Stage definitions ─────────────────────────────────────────────────────────
const STAGE_DEFS = [
  { name: 'Discovery',    key: 'raw',            desc: 'Fresh articles' },
  { name: 'Viral Score',  key: 'approved',       desc: 'Scored queue' },
  { name: 'Dedup',        key: 'ranked',         desc: 'Unique ranked' },
  { name: 'Top-30 Gate',  key: 'approved_unique',desc: 'Cost gate', isCostGate: true },
  { name: 'Summarise',    key: 'top30_selected', desc: 'Caption gen' },
  { name: 'Image Gen',    key: 'summarised',     desc: 'Render queue' },
  { name: 'Publish',      key: 'image_ready',    desc: 'Ready to post' },
] as const;

// ── Helpers ───────────────────────────────────────────────────────────────────
function secondsSince(date: Date) {
  return Math.round((Date.now() - date.getTime()) / 1000);
}

function StageCard({
  name, count, isCostGate, isRunning, desc,
}: {
  name: string; count: number; isCostGate?: boolean;
  isRunning: boolean; desc: string;
}) {
  return (
    <Card
      className={`min-w-[130px] flex-shrink-0 relative overflow-hidden transition-all duration-300 ${
        isCostGate
          ? 'border-red-400 shadow-red-100 shadow-md'
          : 'border-border shadow-sm'
      }`}
    >
      {/* Pulsing activity indicator */}
      {isRunning && count > 0 && (
        <span className="absolute top-2.5 right-2.5 flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
        </span>
      )}
      <CardHeader className="p-3 pb-1">
        <CardTitle className="text-[11px] font-bold text-muted-foreground uppercase tracking-widest leading-tight">
          {name}
          {isCostGate && (
            <span className="ml-1 text-[9px] text-red-500 font-bold tracking-normal">
              COST GATE
            </span>
          )}
        </CardTitle>
        <p className="text-[10px] text-muted-foreground/70 mt-0.5">{desc}</p>
      </CardHeader>
      <CardContent className="p-3 pt-1">
        <div
          className={`text-4xl font-black tabular-nums transition-colors duration-300 ${
            count > 0 ? 'text-green-500' : 'text-muted-foreground/25'
          }`}
        >
          {count}
        </div>
      </CardContent>
    </Card>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function Index() {
  const [stages, setStages]           = useState<Record<string, number>>({});
  const [logs, setLogs]               = useState<any[]>([]);
  const [pipelineStatus, setStatus]   = useState<any>({ is_running: false });
  const [lastRefreshed, setLast]      = useState<Date>(new Date());
  const [secondsAgo, setSecondsAgo]   = useState(0);
  const [isTriggering, setTriggering] = useState(false);

  // ── Ticker: "X seconds ago" ──────────────────────────────────────────────
  useEffect(() => {
    const ticker = setInterval(() => setSecondsAgo(secondsSince(lastRefreshed)), 1000);
    return () => clearInterval(ticker);
  }, [lastRefreshed]);

  // ── Data fetch ────────────────────────────────────────────────────────────
  const fetchData = useCallback(async () => {
    try {
      const [stagesData, logsData, statusData] = await Promise.allSettled([
        fetchPipelineStages(),
        fetchPipelineLogs(),
        fetchPipelineStatus(),
      ]);
      if (stagesData.status === 'fulfilled') setStages(stagesData.value ?? {});
      if (logsData.status === 'fulfilled')   setLogs((logsData.value ?? []).slice(0, 10));
      if (statusData.status === 'fulfilled') setStatus(statusData.value ?? { is_running: false });
      setLast(new Date());
      setSecondsAgo(0);
    } catch (err) {
      console.error('Pipeline data fetch failed', err);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // ── Run pipeline ──────────────────────────────────────────────────────────
  const handleRun = async () => {
    setTriggering(true);
    try {
      const result = await runPipeline();
      if (result?.statusCode === 409) {
        toast.info('Pipeline is already running');
      } else {
        toast.success('Pipeline triggered successfully');
        await fetchData();
      }
    } catch (err: any) {
      toast.error(`Failed to run pipeline: ${err.message}`);
    } finally {
      setTriggering(false);
    }
  };

  const isRunning = pipelineStatus?.is_running;

  // ── Derived totals ────────────────────────────────────────────────────────
  const totalToday   = (stages['raw'] ?? 0) + (stages['approved'] ?? 0);
  const published    = stages['published'] ?? 0;
  const discarded    = stages['discarded'] ?? 0;
  const failed       = stages['failed'] ?? 0;

  return (
    <div className="p-6 lg:p-8 max-w-screen-2xl mx-auto space-y-6 animate-in fade-in duration-500">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black tracking-tight">Pipeline Monitor</h1>
          <p className="text-sm text-muted-foreground flex items-center gap-1.5 mt-0.5">
            <Clock className="w-3.5 h-3.5" />
            Updated {secondsAgo < 5 ? 'just now' : `${secondsAgo}s ago`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge
            variant={isRunning ? 'default' : 'secondary'}
            className={`text-xs px-2.5 py-1 ${isRunning ? 'bg-green-500 hover:bg-green-500' : ''}`}
          >
            {isRunning ? (
              <><Loader2 className="w-3 h-3 mr-1 animate-spin" />Running</>
            ) : (
              <><CheckCircle2 className="w-3 h-3 mr-1" />Idle</>
            )}
          </Badge>
          <Button
            onClick={handleRun}
            disabled={isTriggering || isRunning}
            size="sm"
            className="gap-2"
          >
            {isTriggering
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Play className="w-4 h-4" />}
            {isTriggering ? 'Triggering…' : '▶ Run Pipeline'}
          </Button>
        </div>
      </div>

      {/* ── Stage Flow ─────────────────────────────────────────────────── */}
      <div className="flex items-stretch gap-1.5 overflow-x-auto pb-2">
        {STAGE_DEFS.map((stage, idx) => (
          <React.Fragment key={stage.key}>
            <StageCard
              name={stage.name}
              count={stages[stage.key] ?? 0}
              isCostGate={stage.isCostGate}
              isRunning={!!isRunning}
              desc={stage.desc}
            />
            {idx < STAGE_DEFS.length - 1 && (
              <div className="flex items-center flex-shrink-0 text-muted-foreground/40">
                <ArrowRight className="w-5 h-5" />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>

      {/* ── Stat cards ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Today',  value: totalToday, color: 'text-foreground' },
          { label: 'Published',    value: published,  color: 'text-green-600' },
          { label: 'Discarded',    value: discarded,  color: 'text-orange-500' },
          { label: 'Failed',       value: failed,     color: 'text-red-600' },
        ].map(({ label, value, color }) => (
          <Card key={label} className="shadow-sm">
            <CardHeader className="p-4 pb-1">
              <CardTitle className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                {label}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-1">
              <div className={`text-4xl font-black ${color}`}>{value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ── Recent Runs ────────────────────────────────────────────────── */}
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle className="flex items-center gap-2 text-base font-bold">
            <Activity className="w-4 h-4 text-muted-foreground" />
            Recent Pipeline Runs
          </CardTitle>
          <Button variant="ghost" size="sm" onClick={fetchData} className="gap-1.5 text-xs">
            <RefreshCw className="w-3.5 h-3.5" />Refresh
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="pl-6">Stage</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead className="text-right">In</TableHead>
                <TableHead className="text-right">Out</TableHead>
                <TableHead className="pr-6">Errors</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground py-10 text-sm">
                    No pipeline runs yet. Click <strong>Run Pipeline</strong> to start.
                  </TableCell>
                </TableRow>
              ) : (
                logs.map((log, i) => {
                  const start    = new Date(log.started_at);
                  const end      = log.completed_at ? new Date(log.completed_at) : null;
                  const durSec   = end ? (end.getTime() - start.getTime()) / 1000 : null;
                  const hasError = log.errors && Number(log.errors) > 0;

                  return (
                    <TableRow key={i} className="text-sm">
                      <TableCell className="pl-6 font-medium capitalize">{log.stage}</TableCell>
                      <TableCell className="text-muted-foreground">{relativeTime(log.started_at)}</TableCell>
                      <TableCell className="text-muted-foreground font-mono text-xs">
                        {formatDurationSec(durSec)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{log.articles_in ?? '—'}</TableCell>
                      <TableCell className="text-right tabular-nums">{log.articles_out ?? '—'}</TableCell>
                      <TableCell className="pr-6">
                        {hasError ? (
                          <span className="flex items-center gap-1 text-red-600 font-semibold text-xs">
                            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                            {log.errors}
                          </span>
                        ) : (
                          <span className="text-muted-foreground/50 text-xs">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
