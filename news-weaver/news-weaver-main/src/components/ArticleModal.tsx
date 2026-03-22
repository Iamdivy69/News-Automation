import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { X, Copy, Check } from "lucide-react";
import { fetchArticle } from "@/lib/api";

interface ArticleModalProps {
  article: any;
  onClose: () => void;
}

const platformTabs = ["twitter", "linkedin", "instagram", "facebook"] as const;

export default function ArticleModal({ article, onClose }: ArticleModalProps) {
  const [activeTab, setActiveTab] = useState<string>("twitter");
  const [copied, setCopied] = useState(false);

  if (!article) return null;

  const { data: fullArticle } = useQuery({
    queryKey: ["article", article.id],
    queryFn: () => fetchArticle(article.id),
    enabled: !!article.id,
    staleTime: 60000,
  });

  const data = fullArticle ?? article;
  const raw = data.summary ?? {};
  const summaries: Record<string, string> = {
    twitter:   raw.twitter_text        ?? "",
    linkedin:  raw.linkedin_text       ?? "",
    instagram: raw.instagram_caption   ?? "",
    facebook:  raw.facebook_text       ?? "",
  };
  const hashtags: string = raw.hashtags ?? "";
  const imageUrl = `/api/articles/${article.id}/image`;

  const handleCopy = () => {
    const text = summaries[activeTab] ?? "";
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm" onClick={onClose}>
      <div
        className="relative mx-4 max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-border bg-card shadow-2xl animate-fade-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Image */}
        <img
          src={imageUrl}
          alt={data.headline}
          className="h-56 w-full rounded-t-xl object-cover"
          onError={(e) => (e.currentTarget.style.display = "none")}
        />

        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute right-3 top-3 rounded-full bg-card/80 p-1.5 text-muted-foreground transition-colors hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="p-6 space-y-4">
          {/* Header */}
          <h2 className="text-xl font-bold leading-tight text-foreground">{data.headline}</h2>

          <div className="flex flex-wrap items-center gap-2">
            {data.source && (
              <span className="platform-badge bg-secondary text-secondary-foreground">{data.source}</span>
            )}
            {data.category && (
              <span className="platform-badge bg-primary/15 text-primary">{data.category}</span>
            )}
            {data.viral_score != null && (
              <span className="text-xs text-muted-foreground">Score: {data.viral_score}</span>
            )}
          </div>

          {/* Platform tabs */}
          <div className="space-y-3">
            <div className="flex gap-1 rounded-lg bg-muted p-1">
              {platformTabs.map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
                    activeTab === tab
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            <div className="relative rounded-lg bg-muted p-4">
              <p className="pr-8 text-sm leading-relaxed text-foreground whitespace-pre-wrap">
                {summaries[activeTab] || "No summary available — run the pipeline to generate social content."}
              </p>
              <button
                onClick={handleCopy}
                className="absolute right-3 top-3 rounded p-1 text-muted-foreground transition-colors hover:text-foreground"
                title="Copy"
              >
                {copied ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {/* Hashtags */}
          {hashtags && (
            <div className="flex flex-wrap gap-1.5 pt-2">
              {hashtags.split(",").map((tag: string) => (
                <span key={tag.trim()} className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                  {tag.trim()}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
