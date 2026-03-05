import { useRef, useCallback, useState } from "react";

interface Props {
  startTime: number;
  endTime: number;
  duration: number;
  onChange: (start: number, end: number) => void;
}

const MIN_CLIP = 0.5;

export function TrimSlider({ startTime, endTime, duration, onChange }: Props) {
  const trackRef = useRef<HTMLDivElement>(null);
  const stateRef = useRef({ start: startTime, end: endTime });
  const [isDragging, setIsDragging] = useState(false);
  const [displayStart, setDisplayStart] = useState(startTime);
  const [displayEnd, setDisplayEnd] = useState(endTime);

  // Sync display when props change externally (undo, etc.) — but not during drag
  if (!isDragging && (displayStart !== startTime || displayEnd !== endTime)) {
    setDisplayStart(startTime);
    setDisplayEnd(endTime);
    stateRef.current = { start: startTime, end: endTime };
  }

  const toPercent = (t: number) => (t / duration) * 100;

  const toTime = useCallback(
    (clientX: number) => {
      const track = trackRef.current;
      if (!track) return 0;
      const rect = track.getBoundingClientRect();
      const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      return Math.round(pct * duration * 10) / 10;
    },
    [duration],
  );

  const handlePointerDown = useCallback(
    (handle: "start" | "end") => (e: React.PointerEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(true);
      stateRef.current = { start: displayStart, end: displayEnd };

      const onMove = (ev: PointerEvent) => {
        const t = toTime(ev.clientX);
        const cur = stateRef.current;

        if (handle === "start") {
          const newStart = Math.max(0, Math.min(t, cur.end - MIN_CLIP));
          stateRef.current = { ...cur, start: newStart };
          setDisplayStart(newStart);
        } else {
          const newEnd = Math.min(duration, Math.max(t, cur.start + MIN_CLIP));
          stateRef.current = { ...cur, end: newEnd };
          setDisplayEnd(newEnd);
        }
      };

      const onUp = () => {
        document.removeEventListener("pointermove", onMove);
        document.removeEventListener("pointerup", onUp);
        setIsDragging(false);
        // Single commit to store — one undo entry for the whole drag
        const final = stateRef.current;
        onChange(final.start, final.end);
      };

      document.addEventListener("pointermove", onMove);
      document.addEventListener("pointerup", onUp);
    },
    [duration, displayStart, displayEnd, toTime, onChange],
  );

  const leftPct = toPercent(displayStart);
  const rightPct = toPercent(displayEnd);

  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-text-muted">
        Trim
      </label>
      <div
        ref={trackRef}
        className="relative h-10 select-none rounded-md bg-surface-lighter"
      >
        {/* Inactive regions */}
        <div
          className="absolute inset-y-0 left-0 rounded-l-md bg-black/30"
          style={{ width: `${leftPct}%` }}
        />
        <div
          className="absolute inset-y-0 right-0 rounded-r-md bg-black/30"
          style={{ width: `${100 - rightPct}%` }}
        />

        {/* Active region */}
        <div
          className="absolute inset-y-0 border-y-2 border-primary/50"
          style={{ left: `${leftPct}%`, right: `${100 - rightPct}%` }}
        />

        {/* Start handle */}
        <div
          className="absolute top-0 bottom-0 z-10 flex w-6 -translate-x-1/2 cursor-ew-resize items-center justify-center"
          style={{ left: `${leftPct}%` }}
          onPointerDown={handlePointerDown("start")}
        >
          <div className="h-full w-1.5 rounded-full bg-primary shadow-md">
            <div className="flex h-full items-center justify-center">
              <div className="h-4 w-0.5 rounded-full bg-white/80" />
            </div>
          </div>
        </div>

        {/* End handle */}
        <div
          className="absolute top-0 bottom-0 z-10 flex w-6 -translate-x-1/2 cursor-ew-resize items-center justify-center"
          style={{ left: `${rightPct}%` }}
          onPointerDown={handlePointerDown("end")}
        >
          <div className="h-full w-1.5 rounded-full bg-primary shadow-md">
            <div className="flex h-full items-center justify-center">
              <div className="h-4 w-0.5 rounded-full bg-white/80" />
            </div>
          </div>
        </div>
      </div>

      {/* Time labels */}
      <div className="mt-1 flex justify-between text-[10px] text-text-muted">
        <span>{displayStart.toFixed(1)}s</span>
        <span className="font-medium text-text">
          {(displayEnd - displayStart).toFixed(1)}s
        </span>
        <span>{displayEnd.toFixed(1)}s</span>
      </div>
    </div>
  );
}
