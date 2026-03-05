import { X } from "lucide-react";
import { ThumbnailImage } from "../shared/ThumbnailImage";
import type { VideoInfo } from "../../types";

interface Props {
  videos: VideoInfo[];
  onRemove?: (index: number) => void;
}

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function VideoFileList({ videos, onRemove }: Props) {
  if (videos.length === 0) return null;

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-text-muted">
        Uploaded Videos ({videos.length})
      </h3>
      <div className="space-y-2">
        {videos.map((v, i) => (
          <div
            key={i}
            className="flex items-center gap-3 rounded-lg bg-surface-light p-3"
          >
            <ThumbnailImage
              src={v.thumbnail_url}
              alt={v.filename}
              className="h-14 w-10 rounded"
            />
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-medium">{v.filename}</p>
              <p className="text-xs text-text-muted">
                {formatDuration(v.duration)} &middot; {v.width}x{v.height} &middot;{" "}
                {v.fps.toFixed(0)}fps
              </p>
            </div>
            {onRemove && (
              <button
                onClick={() => onRemove(i)}
                className="rounded p-1 text-text-muted hover:bg-surface-lighter hover:text-error"
              >
                <X size={16} />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
