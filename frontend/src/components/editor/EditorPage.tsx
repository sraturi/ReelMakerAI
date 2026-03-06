import { useState, useEffect } from "react";
import { Play, Loader2, Undo2, Redo2 } from "lucide-react";
import { ClipCardList } from "./ClipCardList";
import { ClipDetailPanel } from "./ClipDetailPanel";
import { OverlayList } from "./OverlayList";
import { TimelineSummary } from "./TimelineSummary";
import { AIActions } from "./AIActions";
import { suggestClip } from "../../api/suggest";
import { startRender } from "../../api/render";
import { useSessionStore } from "../../store/useSessionStore";
import { useEditorStore } from "../../store/useEditorStore";
import { useUIStore } from "../../store/useUIStore";
import type { ClipSuggestion, EditingPlan } from "../../types";

export function EditorPage() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const plan = useSessionStore((s) => s.plan);
  const settings = useSessionStore((s) => s.settings);
  const clips = useEditorStore((s) => s.clips);
  const overlays = useEditorStore((s) => s.overlays);
  const selectedClipId = useEditorStore((s) => s.selectedClipId);
  const replaceClip = useEditorStore((s) => s.replaceClip);
  const undo = useEditorStore((s) => s.undo);
  const redo = useEditorStore((s) => s.redo);
  const pastLen = useEditorStore((s) => s._past.length);
  const futureLen = useEditorStore((s) => s._future.length);
  const setStep = useUIStore((s) => s.setStep);
  const setLoading = useUIStore((s) => s.setLoading);
  const setError = useUIStore((s) => s.setError);
  const setActiveJobId = useUIStore((s) => s.setActiveJobId);
  const clearLogs = useUIStore((s) => s.clearLogs);

  // Keyboard shortcuts for undo/redo
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        useEditorStore.getState().undo();
      } else if (mod && e.key === "z" && e.shiftKey) {
        e.preventDefault();
        useEditorStore.getState().redo();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const [suggestModal, setSuggestModal] = useState<{
    clipIndex: number;
    suggestions: ClipSuggestion[];
  } | null>(null);
  const [suggestLoading, setSuggestLoading] = useState(false);

  async function handleSuggest(clipIndex: number) {
    if (!sessionId || !plan) return;
    setSuggestLoading(true);
    try {
      const currentPlan: EditingPlan = {
        ...plan,
        clips,
        text_overlays: overlays,
      };
      const result = await suggestClip(sessionId, clipIndex, currentPlan);
      setSuggestModal({ clipIndex, suggestions: result.suggestions || [] });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
    setSuggestLoading(false);
  }

  function handlePickSuggestion(suggestion: ClipSuggestion) {
    if (!suggestModal) return;
    const clip = clips[suggestModal.clipIndex];
    if (clip) {
      replaceClip(clip.clip_id, {
        source_video: suggestion.source_video,
        source_index: suggestion.source_index,
        start_time: suggestion.start_time,
        end_time: suggestion.end_time,
        thumbnail_url: suggestion.thumbnail_url,
        video_url: suggestion.video_url,
      });
    }
    setSuggestModal(null);
  }

  async function handleRender() {
    if (!sessionId) return;
    clearLogs();
    setLoading(true, "Rendering reel...");
    try {
      const currentPlan: EditingPlan = {
        music_track: plan?.music_track || "",
        total_duration: plan?.total_duration || 30,
        description: plan?.description || "",
        clips,
        text_overlays: overlays,
      };
      const { job_id } = await startRender(
        sessionId,
        currentPlan,
        settings.audio_mode,
        settings.transition_style,
      );
      setActiveJobId(job_id);
      setStep("render");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold">Edit Your Reel</h1>
          <div className="flex items-center gap-1">
            <button
              onClick={undo}
              disabled={pastLen === 0}
              className="rounded-lg p-1.5 text-text-muted hover:bg-surface-light disabled:opacity-30"
              title="Undo (Ctrl+Z)"
            >
              <Undo2 size={16} />
            </button>
            <button
              onClick={redo}
              disabled={futureLen === 0}
              className="rounded-lg p-1.5 text-text-muted hover:bg-surface-light disabled:opacity-30"
              title="Redo (Ctrl+Shift+Z)"
            >
              <Redo2 size={16} />
            </button>
          </div>
        </div>
        {plan?.description && (
          <p className="hidden text-sm text-text-muted sm:block">{plan.description}</p>
        )}
      </div>

      <AIActions />
      <TimelineSummary />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Clip list (2/3) */}
        <div className="space-y-4 lg:col-span-2">
          <ClipCardList onSuggest={handleSuggest} />
          <OverlayList />
        </div>

        {/* Detail sidebar (1/3) */}
        <div className="lg:col-span-1">
          {selectedClipId ? (
            <ClipDetailPanel />
          ) : (
            <div className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-text-muted">
              Click a clip to edit its details
            </div>
          )}
        </div>
      </div>

      {/* Render CTA */}
      <button
        onClick={handleRender}
        disabled={clips.length === 0}
        className="gradient-bg flex w-full items-center justify-center gap-2 rounded-xl py-3.5 text-base font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Play size={20} />
        Render Reel
      </button>

      {/* Suggest modal */}
      {suggestLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="flex items-center gap-3 rounded-xl bg-surface p-6">
            <Loader2 className="animate-spin text-primary" size={20} />
            <span>Finding alternatives...</span>
          </div>
        </div>
      )}

      {suggestModal && !suggestLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-xl bg-surface p-6 shadow-2xl">
            <h3 className="mb-4 text-lg font-semibold">Alternative Clips</h3>
            <div className="space-y-2">
              {suggestModal.suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => handlePickSuggestion(s)}
                  className="flex w-full items-center gap-3 rounded-lg bg-surface-light p-3 text-left hover:bg-surface-lighter"
                >
                  {s.thumbnail_url && (
                    <img
                      src={s.thumbnail_url}
                      alt=""
                      className="h-16 w-10 flex-shrink-0 rounded object-cover"
                    />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">
                      {s.source_video} [{s.start_time.toFixed(1)}s – {s.end_time.toFixed(1)}s]
                    </div>
                    <p className="mt-1 text-xs text-text-muted">{s.reason}</p>
                  </div>
                </button>
              ))}
            </div>
            <button
              onClick={() => setSuggestModal(null)}
              className="mt-4 w-full rounded-lg py-2 text-sm text-text-muted hover:bg-surface-light"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
