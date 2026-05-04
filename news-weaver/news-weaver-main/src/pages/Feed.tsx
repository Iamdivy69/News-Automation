import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import {
  RefreshCw, ImageIcon, Check, X, Loader2, ChevronDown,
  ChevronUp, Flame, ExternalLink,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  fetchTop30, patchArticle, regenerateImage,
  discardArticle, relativeTime,
} from '@/lib/api';

// ── Types ─────────────────────────────────────────────────────────────────────
type Article = {
  id: number;
  headline: string;
  source: string;
  category: string;
  viral_score: number;
  status: string;
  image_url: string | null;
  captions: Record<string, string> | null;
  processing_stage: string;
  created_at?: string;
};

// ── Helpers ───────────────────────────────────────────────────────────────────
const STATUS_FILTERS = ['All', 'top30_selected', 'summarised', 'image_ready', 'published', 'failed'] as const;
type Filter = typeof STATUS_FILTERS[number];

function viralColor(score: number) {
  if (score > 70) return 'bg-red-500 text-white';
  if (score > 50) return 'bg-orange-400 text-white';
  return 'bg-muted text-muted-foreground';
}

function statusColor(status: string) {
  const map: Record<string, string> = {
    published:     'bg-green-500/15 text-green-700 border-green-500/30',
    image_ready:   'bg-blue-500/15 text-blue-700 border-blue-500/30',
    summarised:    'bg-purple-500/15 text-purple-700 border-purple-500/30',
    top30_selected:'bg-yellow-500/15 text-yellow-700 border-yellow-500/30',
    failed:        'bg-red-500/15 text-red-700 border-red-500/30',
    discarded:     'bg-gray-500/15 text-gray-500 border-gray-500/30',
  };
  return map[status] ?? 'bg-muted text-muted-foreground border-border';
}

const CAPTION_PLATFORMS = ['twitter', 'instagram', 'linkedin', 'facebook'] as const;

// ── Caption editor ────────────────────────────────────────────────────────────
function CaptionEditor({
  articleId, captions, onSaved,
}: {
  articleId: number;
  captions: Record<string, string> | null;
  onSaved: (updated: Record<string, string>) => void;
}) {
  const [local, setLocal] = useState<Record<string, string>>(captions ?? {});
  const [saving, setSaving] = useState(false);

  const handleBlur = async (platform: string) => {
    if (local[platform] === (captions ?? {})[platform]) return; // no change
    setSaving(true);
    try {
      await patchArticle(articleId, { captions: local });
      onSaved(local);
      toast.success(`${platform} caption saved`);
    } catch {
      toast.error(`Failed to save ${platform} caption`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Tabs defaultValue="twitter">
      <TabsList className="h-8 text-xs mb-2">
        {CAPTION_PLATFORMS.map(p => (
          <TabsTrigger key={p} value={p} className="capitalize text-xs px-2 h-7">{p}</TabsTrigger>
        ))}
      </TabsList>
      {CAPTION_PLATFORMS.map(p => (
        <TabsContent key={p} value={p} className="mt-0">
          <Textarea
            className="text-xs resize-none h-20 leading-relaxed"
            placeholder={`${p.charAt(0).toUpperCase() + p.slice(1)} caption…`}
            value={local[p] ?? ''}
            onChange={e => setLocal(prev => ({ ...prev, [p]: e.target.value }))}
            onBlur={() => handleBlur(p)}
          />
        </TabsContent>
      ))}
      {saving && (
        <p className="text-[10px] text-muted-foreground flex items-center gap-1 mt-1">
          <Loader2 className="w-2.5 h-2.5 animate-spin" />Saving…
        </p>
      )}
    </Tabs>
  );
}

// ── Article Card ──────────────────────────────────────────────────────────────
function ArticleCard({
  article, onUpdate, onDiscard,
}: {
  article: Article;
  onUpdate: (id: number, patch: Partial<Article>) => void;
  onDiscard: (id: number) => void;
}) {
  const [regenLoading, setRegenLoading] = useState(false);
  const [approveLoading, setApproveLoading] = useState(false);
  const [discardLoading, setDiscardLoading] = useState(false);
  const [captionsOpen, setCaptionsOpen] = useState(false);
  const [fading, setFading] = useState(false);
  const headlineRef = useRef<HTMLDivElement>(null);

  const handleHeadlineBlur = async () => {
    const newVal = headlineRef.current?.innerText?.trim();
    if (!newVal || newVal === article.headline) return;
    try {
      await patchArticle(article.id, { headline: newVal });
      onUpdate(article.id, { headline: newVal });
      toast.success('Headline updated');
    } catch {
      toast.error('Failed to update headline');
      if (headlineRef.current) headlineRef.current.innerText = article.headline;
    }
  };

  const handleRegen = async () => {
    setRegenLoading(true);
    try {
      const result = await regenerateImage(article.id);
      onUpdate(article.id, { image_url: result.image_url || `/api/articles/${article.id}/image` });
      toast.success('Image regenerated');
    } catch {
      toast.error('Image regeneration failed');
    } finally {
      setRegenLoading(false);
    }
  };

  const handleApprove = async () => {
    setApproveLoading(true);
    try {
      // patch article to mark approved (sets processing_stage)
      await patchArticle(article.id, { processing_stage: 'approved' });
      onUpdate(article.id, { status: 'top30_selected' });
      toast.success('Article approved');
    } catch {
      toast.error('Failed to approve article');
    } finally {
      setApproveLoading(false);
    }
  };

  const handleDiscard = async () => {
    setDiscardLoading(true);
    try {
      await discardArticle(article.id);
      setFading(true);
      setTimeout(() => onDiscard(article.id), 400);
      toast.success('Article discarded');
    } catch {
      toast.error('Failed to discard article');
      setDiscardLoading(false);
    }
  };

  const imageUrl = article.image_url
    ? (article.image_url.startsWith('/api') || article.image_url.startsWith('http')
      ? article.image_url
      : `/api/articles/${article.id}/image`)
    : null;

  return (
    <Card
      className={`overflow-hidden transition-all duration-400 shadow-sm hover:shadow-md ${
        fading ? 'opacity-0 scale-95' : 'opacity-100'
      }`}
    >
      {/* Image thumbnail */}
      <div className="relative bg-muted aspect-video overflow-hidden">
        {regenLoading && (
          <div className="absolute inset-0 bg-background/70 flex items-center justify-center z-10">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        )}
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={article.headline}
            className="w-full h-full object-cover"
            onError={e => {
              const t = e.target as HTMLImageElement;
              if (!t.src.includes('/api/articles/')) {
                t.src = `/api/articles/${article.id}/image`;
              } else {
                t.style.display = 'none';
              }
            }}
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-muted-foreground">
            <ImageIcon className="w-10 h-10 opacity-30" />
            <span className="text-xs">No image yet — click Regen</span>
          </div>
        )}
        {/* Viral score badge */}
        <div className="absolute top-2 right-2">
          <span className={`text-[11px] font-bold rounded px-1.5 py-0.5 flex items-center gap-0.5 ${viralColor(article.viral_score)}`}>
            <Flame className="w-2.5 h-2.5" />
            {Math.round(article.viral_score)}
          </span>
        </div>
      </div>

      <CardContent className="p-4 space-y-3">
        {/* Headline — inline editable */}
        <div
          ref={headlineRef}
          contentEditable
          suppressContentEditableWarning
          onBlur={handleHeadlineBlur}
          className="text-sm font-bold leading-snug outline-none focus:ring-1 focus:ring-primary/50 rounded px-1 -mx-1 cursor-text hover:bg-muted/50 transition-colors"
        >
          {article.headline}
        </div>

        {/* Metadata row */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-muted-foreground font-medium">{article.source}</span>
          {article.category && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">{article.category}</Badge>
          )}
          <Badge className={`text-[10px] px-1.5 py-0 h-4 border ${statusColor(article.status)}`}>
            {article.status.replace(/_/g, ' ')}
          </Badge>
        </div>

        {/* Captions collapsible */}
        <div>
          <button
            onClick={() => setCaptionsOpen(!captionsOpen)}
            className="flex items-center gap-1 text-[11px] font-semibold text-muted-foreground hover:text-foreground transition-colors"
          >
            {captionsOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            Captions
          </button>
          {captionsOpen && (
            <div className="mt-2">
              <CaptionEditor
                articleId={article.id}
                captions={article.captions}
                onSaved={c => onUpdate(article.id, { captions: c })}
              />
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="flex items-center gap-1.5 pt-1 border-t border-border">
          <Button
            size="sm"
            variant="outline"
            className="flex-1 h-7 text-xs gap-1"
            onClick={handleRegen}
            disabled={regenLoading}
          >
            {regenLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            Regen
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="flex-1 h-7 text-xs gap-1 text-green-700 border-green-300 hover:bg-green-50"
            onClick={handleApprove}
            disabled={approveLoading || article.status === 'published'}
          >
            {approveLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
            Approve
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="flex-1 h-7 text-xs gap-1 text-red-700 border-red-300 hover:bg-red-50"
            onClick={handleDiscard}
            disabled={discardLoading}
          >
            {discardLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
            Discard
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function Feed() {
  const [articles, setArticles]   = useState<Article[]>([]);
  const [loading, setLoading]     = useState(true);
  const [filter, setFilter]       = useState<Filter>('All');
  const [lastRefreshed, setLast]  = useState<Date>(new Date());

  const load = useCallback(async () => {
    try {
      const data = await fetchTop30();
      setArticles(Array.isArray(data) ? data : []);
      setLast(new Date());
    } catch {
      toast.error('Failed to load top-30 articles');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, [load]);

  const handleUpdate = (id: number, patch: Partial<Article>) => {
    setArticles(prev => prev.map(a => a.id === id ? { ...a, ...patch } : a));
  };

  const handleDiscard = (id: number) => {
    setArticles(prev => prev.filter(a => a.id !== id));
  };

  const filtered = filter === 'All'
    ? articles
    : articles.filter(a => a.status === filter);

  return (
    <div className="p-6 lg:p-8 max-w-screen-2xl mx-auto space-y-6 animate-in fade-in duration-500">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-black tracking-tight">Top 30 Articles</h1>
          <Badge variant="secondary" className="text-sm font-bold px-2.5">
            {articles.length}
          </Badge>
        </div>
        <Button variant="outline" size="sm" onClick={load} className="gap-2 self-start">
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh · {relativeTime(lastRefreshed.toISOString())}
        </Button>
      </div>

      {/* Filter tabs */}
      <div className="flex flex-wrap gap-1.5">
        {STATUS_FILTERS.map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-full text-xs font-semibold transition-colors ${
              filter === f
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            {f === 'All' ? 'All' : f.replace(/_/g, ' ')}
            {f === 'All'
              ? ` (${articles.length})`
              : ` (${articles.filter(a => a.status === f).length})`}
          </button>
        ))}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="overflow-hidden">
              <Skeleton className="aspect-video w-full" />
              <CardContent className="p-4 space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
                <Skeleton className="h-3 w-1/3" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center text-muted-foreground gap-3">
          <ExternalLink className="w-10 h-10 opacity-30" />
          <p className="text-lg font-semibold">No articles in Top 30 yet.</p>
          <p className="text-sm">Run the pipeline to populate this view.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {filtered.map(article => (
            <ArticleCard
              key={article.id}
              article={article}
              onUpdate={handleUpdate}
              onDiscard={handleDiscard}
            />
          ))}
        </div>
      )}
    </div>
  );
}
