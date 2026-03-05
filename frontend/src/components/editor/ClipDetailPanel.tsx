import { useCallback } from "react";
import { X, Volume2, VolumeX } from "lucide-react";
import { VideoClipPlayer } from "../shared/VideoClipPlayer";
import { TransitionPicker } from "./TransitionPicker";
import { KenBurnsPicker } from "./KenBurnsPicker";
import { TrimSlider } from "./TrimSlider";
import { LayoutPicker } from "./LayoutPicker";
import { CompositeEditor } from "./CompositeEditor";
import { CompositePreview } from "./CompositePreview";
import { useEditorStore } from "../../store/useEditorStore";
import { useSessionStore } from "../../store/useSessionStore";
import type { ClipPlan, SubSource } from "../../types";

const LAYOUT_SOURCE_COUNT: Record<string, number> = {
  single: 0,
  split_v: 2,
  split_h: 2,
  pip: 2,
  grid: 4,
};

const LAYOUT_POSITIONS: Record<string, string[]> = {
  split_v: ["top", "bottom"],
  split_h: ["left", "right"],
  pip: ["main", "overlay"],
  grid: ["tl", "tr", "bl", "br"],
};

export function ClipDetailPanel() {
  const clips = useEditorStore((s) => s.clips);
  const selectedClipId = useEditorStore((s) => s.selectedClipId);
  const selectClip = useEditorStore((s) => s.selectClip);
  const updateClip = useEditorStore((s) => s.updateClip);
  const videos = useSessionStore((s) => s.videos);

  const sessionId = useSessionStore((s) => s.sessionId);

  const clip = clips.find((c) => c.clip_id === selectedClipId);
  if (!clip) return null;

  const sourceVideo = videos[clip.source_index];
  const maxDuration = sourceVideo?.duration || clip.end_time;
  const isComposite = clip.layout && clip.layout !== "single" && clip.sub_sources?.length > 0;

  const update = (u: Partial<ClipPlan>) => updateClip(clip.clip_id, u);

  const handleLayoutChange = (newLayout: string) => {
    if (newLayout === "single") {
      // Revert to single: use first sub-source as primary if available
      const first = clip.sub_sources?.[0];
      if (first) {
        update({
          layout: "single",
          sub_sources: [],
          source_video: first.source_video,
          source_index: first.source_index,
          start_time: first.start_time,
          end_time: first.end_time,
          thumbnail_url: first.thumbnail_url,
          video_url: first.video_url,
        });
      } else {
        update({ layout: "single", sub_sources: [] });
      }
      return;
    }

    // Switch to composite: auto-populate sub_sources
    const count = LAYOUT_SOURCE_COUNT[newLayout] || 2;
    const positions = LAYOUT_POSITIONS[newLayout] || [];
    const subs: SubSource[] = [];

    // First sub-source from current clip
    const midTime0 = (clip.start_time + clip.end_time) / 2;
    subs.push({
      source_video: clip.source_video,
      source_index: clip.source_index,
      start_time: clip.start_time,
      end_time: clip.end_time,
      position: positions[0] || "auto",
      thumbnail_url: clip.thumbnail_url || `/api/thumbnail/${sessionId}/${clip.source_index}/${midTime0.toFixed(2)}`,
      video_url: clip.video_url || `/api/video/${sessionId}/${clip.source_index}`,
    });

    // Fill remaining from other available videos
    for (let j = 1; j < count; j++) {
      // Pick a different video if possible
      const vidIdx = (clip.source_index + j) % videos.length;
      const vid = videos[vidIdx];
      const start = 0;
      const end = Math.min(vid.duration, clip.end_time - clip.start_time);
      const midThumb = (start + end) / 2;
      subs.push({
        source_video: vid.filename,
        source_index: vidIdx,
        start_time: start,
        end_time: end,
        position: positions[j] || "auto",
        thumbnail_url: `/api/thumbnail/${sessionId}/${vidIdx}/${midThumb.toFixed(2)}`,
        video_url: `/api/video/${sessionId}/${vidIdx}`,
      });
    }

    update({
      layout: newLayout,
      sub_sources: subs,
      ken_burns: "none",
    });
  };

  const handleTrimChange = useCallback(
    (start: number, end: number) => {
      updateClip(clip.clip_id, {
        start_time: start,
        end_time: end,
      });
    },
    [clip.clip_id, updateClip],
  );

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

      {/* Playable video preview or composite preview */}
      {isComposite ? (
        <CompositePreview
          layout={clip.layout}
          subSources={clip.sub_sources}
          className="mb-4 aspect-[9/16] w-full rounded-lg"
        />
      ) : (
        <VideoClipPlayer
          key={`${clip.clip_id}-${clip.start_time}-${clip.end_time}`}
          videoUrl={clip.video_url}
          startTime={clip.start_time}
          endTime={clip.end_time}
          thumbnailUrl={clip.thumbnail_url}
          mode="controls"
          muted={clip.audio === "mute"}
          className="mb-4 aspect-[9/16] w-full rounded-lg"
        />
      )}

      <div className="mb-3 text-xs text-text-muted">
        <p>
          <span className="font-medium text-text">Source:</span> {clip.source_video}
        </p>
      </div>

      <div className="space-y-4">
        <LayoutPicker
          value={clip.layout || "single"}
          onChange={handleLayoutChange}
        />

        {isComposite ? (
          <CompositeEditor
            layout={clip.layout}
            subSources={clip.sub_sources}
            videos={videos}
            sessionId={sessionId || ""}
            onChange={(subs) => update({ sub_sources: subs })}
          />
        ) : (
          <>
            <TrimSlider
              startTime={clip.start_time}
              endTime={clip.end_time}
              duration={maxDuration}
              onChange={handleTrimChange}
            />

            <KenBurnsPicker
              value={clip.ken_burns}
              onChange={(v) => update({ ken_burns: v })}
            />
          </>
        )}

        <TransitionPicker
          value={clip.transition}
          onChange={(v) => update({ transition: v })}
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
