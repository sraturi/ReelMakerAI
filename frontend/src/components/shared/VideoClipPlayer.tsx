import { useRef, useEffect, useState, useCallback } from "react";
import { Play, Pause, RotateCcw, Volume2, VolumeX } from "lucide-react";

interface Props {
  videoUrl: string;
  startTime: number;
  endTime: number;
  thumbnailUrl?: string;
  className?: string;
  /** "hover" = play on hover (for cards), "controls" = full controls (for detail panel) */
  mode?: "hover" | "controls";
  muted?: boolean;
}

export function VideoClipPlayer({
  videoUrl,
  startTime,
  endTime,
  thumbnailUrl,
  className = "",
  mode = "controls",
  muted = true,
}: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [localMuted, setLocalMuted] = useState(muted);

  // Sync localMuted when the prop changes (e.g. user toggles Keep Audio / Mute)
  useEffect(() => {
    setLocalMuted(muted);
  }, [muted]);

  // Imperatively set video.muted — React's `muted` JSX attribute doesn't
  // reliably update the DOM property (known React issue).
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.muted = localMuted;
    }
  }, [localMuted]);

  // Clamp playback to the clip range
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      if (video.currentTime >= endTime) {
        video.pause();
        video.currentTime = startTime;
        setPlaying(false);
      }
    };

    video.addEventListener("timeupdate", handleTimeUpdate);
    return () => video.removeEventListener("timeupdate", handleTimeUpdate);
  }, [startTime, endTime]);

  // When metadata loads, seek to start
  const handleLoadedMetadata = useCallback(() => {
    const video = videoRef.current;
    if (video) {
      video.currentTime = startTime;
      setLoaded(true);
    }
  }, [startTime]);

  // Hover mode: play on mouseenter, pause on mouseleave
  const handleMouseEnter = useCallback(() => {
    if (mode !== "hover") return;
    setHovered(true);
    const video = videoRef.current;
    if (video && loaded) {
      video.currentTime = startTime;
      video.play().catch(() => {});
      setPlaying(true);
    }
  }, [mode, loaded, startTime]);

  const handleMouseLeave = useCallback(() => {
    if (mode !== "hover") return;
    setHovered(false);
    const video = videoRef.current;
    if (video) {
      video.pause();
      video.currentTime = startTime;
      setPlaying(false);
    }
  }, [mode, startTime]);

  // Controls mode: toggle play/pause
  const togglePlay = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    if (playing) {
      video.pause();
      setPlaying(false);
    } else {
      // Unmute on explicit user play gesture so browser allows audio
      video.muted = localMuted;
      if (video.currentTime >= endTime || video.currentTime < startTime) {
        video.currentTime = startTime;
      }
      video.play().catch(() => {});
      setPlaying(true);
    }
  }, [playing, startTime, endTime, localMuted]);

  const restart = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = startTime;
    video.play().catch(() => {});
    setPlaying(true);
  }, [startTime]);

  const toggleMute = useCallback(() => {
    setLocalMuted((m) => !m);
  }, []);

  // Use media fragment for initial load hint
  const src = `${videoUrl}#t=${startTime.toFixed(2)},${endTime.toFixed(2)}`;

  return (
    <div
      className={`group/player relative overflow-hidden bg-black ${className}`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {/* Poster thumbnail shown when not playing in hover mode */}
      {mode === "hover" && thumbnailUrl && !hovered && (
        <img
          src={thumbnailUrl}
          alt=""
          className="absolute inset-0 h-full w-full object-cover"
        />
      )}

      <video
        ref={videoRef}
        src={src}
        playsInline
        preload={mode === "hover" ? "none" : "metadata"}
        onLoadedMetadata={handleLoadedMetadata}
        className={`h-full w-full object-cover ${
          mode === "hover" && !hovered ? "opacity-0" : "opacity-100"
        }`}
      />

      {/* Hover mode: play icon overlay */}
      {mode === "hover" && !hovered && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="rounded-full bg-black/50 p-1.5">
            <Play size={12} className="text-white" fill="white" />
          </div>
        </div>
      )}

      {/* Controls mode: play/pause + mute toggle */}
      {mode === "controls" && (
        <div className="absolute inset-x-0 bottom-0 flex items-center gap-1 bg-gradient-to-t from-black/70 to-transparent p-2 opacity-0 transition-opacity group-hover/player:opacity-100">
          <button
            onClick={togglePlay}
            className="rounded-full bg-white/20 p-1.5 backdrop-blur-sm hover:bg-white/30"
          >
            {playing ? (
              <Pause size={14} className="text-white" />
            ) : (
              <Play size={14} className="text-white" fill="white" />
            )}
          </button>
          <button
            onClick={restart}
            className="rounded-full bg-white/20 p-1.5 backdrop-blur-sm hover:bg-white/30"
          >
            <RotateCcw size={14} className="text-white" />
          </button>
          <button
            onClick={toggleMute}
            className="rounded-full bg-white/20 p-1.5 backdrop-blur-sm hover:bg-white/30"
            title={localMuted ? "Unmute" : "Mute"}
          >
            {localMuted ? (
              <VolumeX size={14} className="text-white" />
            ) : (
              <Volume2 size={14} className="text-white" />
            )}
          </button>
          <span className="ml-auto text-[10px] text-white/70">
            {(endTime - startTime).toFixed(1)}s
          </span>
        </div>
      )}
    </div>
  );
}
