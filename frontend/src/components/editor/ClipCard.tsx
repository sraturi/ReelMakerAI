import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Sparkles, Trash2, Volume2, VolumeX } from "lucide-react";
import { VideoClipPlayer } from "../shared/VideoClipPlayer";
import type { ClipPlan } from "../../types";

interface Props {
  clip: ClipPlan;
  index: number;
  isSelected: boolean;
  onSelect: () => void;
  onRemove: () => void;
  onSuggest: () => void;
}

export function ClipCard({
  clip,
  index,
  isSelected,
  onSelect,
  onRemove,
  onSuggest,
}: Props) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: clip.clip_id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const duration = (clip.end_time - clip.start_time).toFixed(1);

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`group relative flex items-center gap-3 rounded-lg border p-3 transition-colors ${
        isDragging
          ? "z-10 border-primary bg-primary/10 shadow-xl"
          : isSelected
            ? "border-primary bg-surface-light"
            : "border-border bg-surface hover:bg-surface-light"
      }`}
      onClick={onSelect}
    >
      {/* Drag handle */}
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab touch-none text-text-muted hover:text-text active:cursor-grabbing"
      >
        <GripVertical size={18} />
      </button>

      {/* Video preview — plays on hover */}
      <VideoClipPlayer
        videoUrl={clip.video_url}
        startTime={clip.start_time}
        endTime={clip.end_time}
        thumbnailUrl={clip.thumbnail_url}
        mode="hover"
        className="h-16 w-10 flex-shrink-0 rounded"
      />

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-primary">#{index + 1}</span>
          <span className="truncate text-sm font-medium">
            {clip.source_video}
          </span>
        </div>
        <p className="text-xs text-text-muted">
          {clip.start_time.toFixed(1)}s – {clip.end_time.toFixed(1)}s ({duration}s)
        </p>
        <div className="mt-1 flex items-center gap-2">
          <span className="rounded bg-surface-lighter px-1.5 py-0.5 text-[10px] font-medium text-text-muted">
            {clip.transition}
          </span>
          {clip.ken_burns !== "none" && (
            <span className="rounded bg-accent/20 px-1.5 py-0.5 text-[10px] font-medium text-accent">
              {clip.ken_burns}
            </span>
          )}
          {clip.audio === "keep_audio" ? (
            <Volume2 size={12} className="text-success" />
          ) : (
            <VolumeX size={12} className="text-text-muted" />
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onSuggest();
          }}
          className="rounded p-1.5 text-text-muted hover:bg-primary/20 hover:text-primary"
          title="Suggest alternative"
        >
          <Sparkles size={14} />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="rounded p-1.5 text-text-muted hover:bg-error/20 hover:text-error"
          title="Remove clip"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}
