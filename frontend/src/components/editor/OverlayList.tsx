import { Plus, Trash2 } from "lucide-react";
import { CaptionEditor } from "./CaptionEditor";
import { useEditorStore } from "../../store/useEditorStore";
import type { TextOverlay } from "../../types";

export function OverlayList() {
  const overlays = useEditorStore((s) => s.overlays);
  const updateOverlay = useEditorStore((s) => s.updateOverlay);
  const removeOverlay = useEditorStore((s) => s.removeOverlay);
  const addOverlay = useEditorStore((s) => s.addOverlay);

  function handleAdd() {
    const id = `overlay-${Date.now()}`;
    const newOverlay: TextOverlay = {
      overlay_id: id,
      text: "New caption",
      start_time: 0,
      end_time: 3,
      position: "center",
      font_size: 64,
      color: "white",
      style: "title",
    };
    addOverlay(newOverlay);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Text Overlays ({overlays.length})</h3>
        <button
          onClick={handleAdd}
          className="flex items-center gap-1 rounded-lg bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary hover:bg-primary/20"
        >
          <Plus size={12} /> Add
        </button>
      </div>

      {overlays.length === 0 && (
        <p className="text-xs text-text-muted">No overlays. Add captions above.</p>
      )}

      {overlays.map((overlay) => (
        <div
          key={overlay.overlay_id}
          className="relative rounded-lg border border-border bg-surface p-3"
        >
          <button
            onClick={() => removeOverlay(overlay.overlay_id)}
            className="absolute right-2 top-2 rounded p-1 text-text-muted hover:bg-error/20 hover:text-error"
          >
            <Trash2 size={14} />
          </button>
          <CaptionEditor
            overlay={overlay}
            onUpdate={(u) => updateOverlay(overlay.overlay_id, u)}
          />
          <div className="mt-2 flex gap-2">
            <div>
              <label className="text-[10px] text-text-muted">Start</label>
              <input
                type="number"
                step="0.5"
                min="0"
                value={overlay.start_time}
                onChange={(e) =>
                  updateOverlay(overlay.overlay_id, {
                    start_time: parseFloat(e.target.value) || 0,
                  })
                }
                className="w-16 rounded border border-border bg-surface-light px-2 py-1 text-xs text-text outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="text-[10px] text-text-muted">End</label>
              <input
                type="number"
                step="0.5"
                min="0"
                value={overlay.end_time}
                onChange={(e) =>
                  updateOverlay(overlay.overlay_id, {
                    end_time: parseFloat(e.target.value) || 3,
                  })
                }
                className="w-16 rounded border border-border bg-surface-light px-2 py-1 text-xs text-text outline-none focus:border-primary"
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
