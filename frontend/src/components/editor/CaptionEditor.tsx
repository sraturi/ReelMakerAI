import { useState } from "react";
import { Sparkles, Loader2 } from "lucide-react";
import { rewriteCaption } from "../../api/caption";
import { useSessionStore } from "../../store/useSessionStore";
import type { TextOverlay, CaptionSuggestion } from "../../types";

interface Props {
  overlay: TextOverlay;
  onUpdate: (updates: Partial<TextOverlay>) => void;
}

export function CaptionEditor({ overlay, onUpdate }: Props) {
  const sessionId = useSessionStore((s) => s.sessionId);
  const [suggestions, setSuggestions] = useState<CaptionSuggestion[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleRewrite() {
    if (!sessionId) return;
    setLoading(true);
    try {
      const result = await rewriteCaption(sessionId, overlay.text);
      setSuggestions(result.suggestions || []);
    } catch {
      // silently handle
    }
    setLoading(false);
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="mb-1 block text-xs font-medium text-text-muted">
          Caption Text
        </label>
        <textarea
          value={overlay.text}
          onChange={(e) => onUpdate({ text: e.target.value })}
          rows={2}
          className="w-full resize-none rounded-lg border border-border bg-surface-light px-3 py-2 text-sm text-text outline-none focus:border-primary"
        />
      </div>

      <div className="flex gap-2">
        {["title", "caption", "highlight"].map((s) => (
          <button
            key={s}
            onClick={() => onUpdate({ style: s })}
            className={`rounded-md px-2 py-1 text-xs font-medium ${
              overlay.style === s
                ? "bg-primary text-white"
                : "bg-surface-lighter text-text-muted hover:text-text"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="flex gap-2">
        {["top", "center", "bottom"].map((p) => (
          <button
            key={p}
            onClick={() => onUpdate({ position: p })}
            className={`rounded-md px-2 py-1 text-xs font-medium ${
              overlay.position === p
                ? "bg-primary text-white"
                : "bg-surface-lighter text-text-muted hover:text-text"
            }`}
          >
            {p}
          </button>
        ))}
      </div>

      <button
        onClick={handleRewrite}
        disabled={loading}
        className="flex items-center gap-1.5 rounded-lg bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/20 disabled:opacity-50"
      >
        {loading ? (
          <Loader2 size={12} className="animate-spin" />
        ) : (
          <Sparkles size={12} />
        )}
        Rewrite with AI
      </button>

      {suggestions.length > 0 && (
        <div className="space-y-1">
          {suggestions.map((s, i) => (
            <button
              key={i}
              onClick={() => {
                onUpdate({ text: s.text, style: s.style });
                setSuggestions([]);
              }}
              className="w-full rounded-lg bg-surface-lighter p-2 text-left text-xs hover:bg-surface-light"
            >
              <span className="font-medium">{s.text}</span>
              <span className="ml-2 text-text-muted">({s.tone})</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
