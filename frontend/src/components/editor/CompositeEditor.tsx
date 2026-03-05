import { TrimSlider } from "./TrimSlider";
import type { SubSource, VideoInfo } from "../../types";

const POSITION_LABELS: Record<string, string[]> = {
  split_v: ["Top", "Bottom"],
  split_h: ["Left", "Right"],
  pip: ["Main", "Overlay"],
  grid: ["Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right"],
};

interface Props {
  layout: string;
  subSources: SubSource[];
  videos: VideoInfo[];
  sessionId: string;
  onChange: (subSources: SubSource[]) => void;
}

export function CompositeEditor({
  layout,
  subSources,
  videos,
  sessionId,
  onChange,
}: Props) {
  const labels = POSITION_LABELS[layout] || [];

  const updateSub = (index: number, updates: Partial<SubSource>) => {
    const next = subSources.map((s, i) => (i === index ? { ...s, ...updates } : s));
    onChange(next);
  };

  const handleSourceChange = (index: number, sourceIndex: number) => {
    const vid = videos[sourceIndex];
    if (!vid) return;
    const midTime = vid.duration / 2;
    const start = Math.max(0, midTime - 1.5);
    const end = Math.min(vid.duration, midTime + 1.5);
    const midThumb = (start + end) / 2;
    updateSub(index, {
      source_video: vid.filename,
      source_index: sourceIndex,
      start_time: start,
      end_time: end,
      thumbnail_url: `/api/thumbnail/${sessionId}/${sourceIndex}/${midThumb.toFixed(2)}`,
      video_url: `/api/video/${sessionId}/${sourceIndex}`,
    });
  };

  const handleTrimChange = (index: number, start: number, end: number) => {
    const sub = subSources[index];
    const midThumb = (start + end) / 2;
    updateSub(index, {
      start_time: start,
      end_time: end,
      thumbnail_url: `/api/thumbnail/${sessionId}/${sub.source_index}/${midThumb.toFixed(2)}`,
    });
  };

  return (
    <div className="space-y-3">
      <label className="block text-xs font-medium text-text-muted">
        Sub-Sources
      </label>
      {subSources.map((sub, i) => {
        const vid = videos[sub.source_index];
        const maxDur = vid?.duration || sub.end_time;

        return (
          <div
            key={i}
            className="rounded-lg border border-border bg-surface-lighter p-3 space-y-2"
          >
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-semibold uppercase text-primary">
                {labels[i] || `Source ${i + 1}`}
              </span>
              {sub.thumbnail_url && (
                <img
                  src={sub.thumbnail_url}
                  alt={labels[i]}
                  className="ml-auto h-8 w-5 rounded object-cover"
                />
              )}
            </div>

            <div>
              <label className="mb-0.5 block text-[10px] text-text-muted">
                Video
              </label>
              <select
                value={sub.source_index}
                onChange={(e) => handleSourceChange(i, Number(e.target.value))}
                className="w-full rounded border border-border bg-surface px-2 py-1 text-xs"
              >
                {videos.map((v, vi) => (
                  <option key={vi} value={vi}>
                    {v.filename} ({v.duration.toFixed(1)}s)
                  </option>
                ))}
              </select>
            </div>

            <TrimSlider
              startTime={sub.start_time}
              endTime={sub.end_time}
              duration={maxDur}
              onChange={(s, e) => handleTrimChange(i, s, e)}
            />
          </div>
        );
      })}
    </div>
  );
}
