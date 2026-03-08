import { useRef, useState } from "react";
import { Play, Trash2, X } from "lucide-react";
import { ThumbnailImage } from "../shared/ThumbnailImage";
import type { VideoInfo } from "../../types";

interface Props {
  videos: VideoInfo[];
  sessionId?: string | null;
  onRemove?: (index: number) => void;
}

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function VideoFileList({ videos, sessionId, onRemove }: Props) {
  const [playingIndex, setPlayingIndex] = useState<number | null>(null);

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
            <button
              type="button"
              onClick={() => sessionId && setPlayingIndex(i)}
              className="group/thumb relative h-14 w-10 flex-shrink-0 rounded overflow-hidden"
              disabled={!sessionId}
            >
              <ThumbnailImage
                src={v.thumbnail_url}
                alt={v.filename}
                className="h-full w-full"
              />
              {sessionId && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 transition-opacity group-hover/thumb:opacity-100">
                  <div className="rounded-full bg-white/90 p-1">
                    <Play size={10} className="text-black" fill="black" />
                  </div>
                </div>
              )}
            </button>
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-medium">{v.filename}</p>
              <p className="text-xs text-text-muted">
                {formatDuration(v.duration)} &middot; {v.width}x{v.height} &middot;{" "}
                {v.fps.toFixed(0)}fps
              </p>
            </div>
            {onRemove && (
              <button
                onClick={() => onRemove(v.index)}
                className="rounded p-1.5 text-text-muted hover:bg-error/10 hover:text-error"
                title="Remove video"
              >
                <Trash2 size={15} />
              </button>
            )}
          </div>
        ))}
      </div>

      {playingIndex !== null && sessionId && (
        <VideoModal
          video={videos[playingIndex]}
          videoUrl={`/api/video/${sessionId}/${videos[playingIndex].index}`}
          onClose={() => setPlayingIndex(null)}
        />
      )}
    </div>
  );
}

function VideoModal({
  video,
  videoUrl,
  onClose,
}: {
  video: VideoInfo;
  videoUrl: string;
  onClose: () => void;
}) {
  const overlayRef = useRef<HTMLDivElement>(null);

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
    >
      <div className="relative w-full max-w-sm">
        <button
          onClick={onClose}
          className="absolute -right-2 -top-10 rounded-full bg-white/10 p-1.5 text-white transition-colors hover:bg-white/20"
        >
          <X size={18} />
        </button>
        <div className="overflow-hidden rounded-xl bg-black shadow-2xl">
          <video
            src={videoUrl}
            controls
            autoPlay
            className="aspect-[9/16] w-full"
          />
        </div>
        <p className="mt-3 text-center text-sm font-medium text-white/80">
          {video.filename}
        </p>
      </div>
    </div>
  );
}
