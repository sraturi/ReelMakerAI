import { X, Volume2, VolumeX } from "lucide-react";
import { VideoClipPlayer } from "../shared/VideoClipPlayer";
import { TransitionPicker } from "./TransitionPicker";
import { KenBurnsPicker } from "./KenBurnsPicker";
import { useEditorStore } from "../../store/useEditorStore";
import type { ClipPlan } from "../../types";

export function ClipDetailPanel() {
  const clips = useEditorStore((s) => s.clips);
  const selectedClipId = useEditorStore((s) => s.selectedClipId);
  const selectClip = useEditorStore((s) => s.selectClip);
  const updateClip = useEditorStore((s) => s.updateClip);

  const clip = clips.find((c) => c.clip_id === selectedClipId);
  if (!clip) return null;

  const update = (u: Partial<ClipPlan>) => updateClip(clip.clip_id, u);

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Clip Details</h3>
        <button
          onClick={() => selectClip(null)}
          className="rounded p-1 text-text-muted hover:bg-surface-lighter"
        >
          <X size={16} />
        </button>
      </div>

      {/* Playable video preview */}
      <VideoClipPlayer
        key={clip.clip_id}
        videoUrl={clip.video_url}
        startTime={clip.start_time}
        endTime={clip.end_time}
        thumbnailUrl={clip.thumbnail_url}
        mode="controls"
        muted={clip.audio === "mute"}
        className="mb-4 aspect-[9/16] w-full rounded-lg"
      />

      <div className="mb-3 text-xs text-text-muted">
        <p>
          <span className="font-medium text-text">Source:</span> {clip.source_video}
        </p>
        <p>
          <span className="font-medium text-text">Range:</span>{" "}
          {clip.start_time.toFixed(1)}s – {clip.end_time.toFixed(1)}s
        </p>
      </div>

      <div className="space-y-4">
        <TransitionPicker
          value={clip.transition}
          onChange={(v) => update({ transition: v })}
        />

        <KenBurnsPicker
          value={clip.ken_burns}
          onChange={(v) => update({ ken_burns: v })}
        />

        <div>
          <label className="mb-1 block text-xs font-medium text-text-muted">
            Audio
          </label>
          <div className="flex gap-2">
            <button
              onClick={() => update({ audio: "keep_audio" })}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium ${
                clip.audio === "keep_audio"
                  ? "bg-success/20 text-success"
                  : "bg-surface-lighter text-text-muted"
              }`}
            >
              <Volume2 size={12} /> Keep Audio
            </button>
            <button
              onClick={() => update({ audio: "mute" })}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium ${
                clip.audio === "mute"
                  ? "bg-surface-lighter text-text"
                  : "bg-surface-lighter text-text-muted"
              }`}
            >
              <VolumeX size={12} /> Mute
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
