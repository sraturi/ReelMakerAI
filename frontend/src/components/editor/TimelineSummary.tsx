import { Clock, Film } from "lucide-react";
import { useEditorStore } from "../../store/useEditorStore";

export function TimelineSummary() {
  const clips = useEditorStore((s) => s.clips);

  const totalDuration = clips.reduce(
    (sum, c) => sum + (c.end_time - c.start_time),
    0,
  );

  return (
    <div className="flex items-center gap-4 rounded-lg bg-surface-light px-4 py-2 text-sm">
      <span className="flex items-center gap-1.5 text-text-muted">
        <Film size={14} />
        {clips.length} clips
      </span>
      <span className="flex items-center gap-1.5 text-text-muted">
        <Clock size={14} />
        {totalDuration.toFixed(1)}s
      </span>
    </div>
  );
}
