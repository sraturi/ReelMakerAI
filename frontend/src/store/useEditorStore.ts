import { create } from "zustand";
import type { ClipPlan, TextOverlay } from "../types";

interface EditorState {
  clips: ClipPlan[];
  overlays: TextOverlay[];
  selectedClipId: string | null;

  setClips: (clips: ClipPlan[]) => void;
  setOverlays: (overlays: TextOverlay[]) => void;
  selectClip: (id: string | null) => void;
  updateClip: (clipId: string, updates: Partial<ClipPlan>) => void;
  removeClip: (clipId: string) => void;
  reorderClips: (fromIndex: number, toIndex: number) => void;
  replaceClip: (clipId: string, newClip: Partial<ClipPlan>) => void;
  updateOverlay: (overlayId: string, updates: Partial<TextOverlay>) => void;
  removeOverlay: (overlayId: string) => void;
  addOverlay: (overlay: TextOverlay) => void;
  reset: () => void;
}

export const useEditorStore = create<EditorState>((set) => ({
  clips: [],
  overlays: [],
  selectedClipId: null,

  setClips: (clips) => set({ clips }),
  setOverlays: (overlays) => set({ overlays }),
  selectClip: (id) => set({ selectedClipId: id }),

  updateClip: (clipId, updates) =>
    set((s) => ({
      clips: s.clips.map((c) =>
        c.clip_id === clipId ? { ...c, ...updates } : c,
      ),
    })),

  removeClip: (clipId) =>
    set((s) => ({
      clips: s.clips.filter((c) => c.clip_id !== clipId),
      selectedClipId:
        s.selectedClipId === clipId ? null : s.selectedClipId,
    })),

  reorderClips: (fromIndex, toIndex) =>
    set((s) => {
      const clips = [...s.clips];
      const [moved] = clips.splice(fromIndex, 1);
      clips.splice(toIndex, 0, moved);
      // Recalculate timeline_start
      let t = 0;
      for (const c of clips) {
        c.timeline_start = Math.round(t * 1000) / 1000;
        t += c.end_time - c.start_time;
      }
      return { clips };
    }),

  replaceClip: (clipId, newClip) =>
    set((s) => ({
      clips: s.clips.map((c) =>
        c.clip_id === clipId ? { ...c, ...newClip } : c,
      ),
    })),

  updateOverlay: (overlayId, updates) =>
    set((s) => ({
      overlays: s.overlays.map((o) =>
        o.overlay_id === overlayId ? { ...o, ...updates } : o,
      ),
    })),

  removeOverlay: (overlayId) =>
    set((s) => ({
      overlays: s.overlays.filter((o) => o.overlay_id !== overlayId),
    })),

  addOverlay: (overlay) =>
    set((s) => ({
      overlays: [...s.overlays, overlay],
    })),

  reset: () =>
    set({ clips: [], overlays: [], selectedClipId: null }),
}));
