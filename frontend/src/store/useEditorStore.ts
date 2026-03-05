import { create } from "zustand";
import type { ClipPlan, TextOverlay } from "../types";

interface Snapshot {
  clips: ClipPlan[];
  overlays: TextOverlay[];
  selectedClipId: string | null;
}

const MAX_HISTORY = 30;

interface EditorState extends Snapshot {
  _past: Snapshot[];
  _future: Snapshot[];

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
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;
  reset: () => void;
}

function snap(s: Snapshot): Snapshot {
  return {
    clips: s.clips,
    overlays: s.overlays,
    selectedClipId: s.selectedClipId,
  };
}

/** Push current state onto past, clear future */
function pushHistory(state: EditorState): Pick<EditorState, "_past" | "_future"> {
  const past = [...state._past, snap(state)];
  if (past.length > MAX_HISTORY) past.shift();
  return { _past: past, _future: [] };
}

export const useEditorStore = create<EditorState>((set, get) => ({
  clips: [],
  overlays: [],
  selectedClipId: null,
  _past: [],
  _future: [],

  setClips: (clips) =>
    set((s) => ({ ...pushHistory(s), clips })),

  setOverlays: (overlays) =>
    set((s) => ({ ...pushHistory(s), overlays })),

  selectClip: (id) => set({ selectedClipId: id }),

  updateClip: (clipId, updates) =>
    set((s) => ({
      ...pushHistory(s),
      clips: s.clips.map((c) =>
        c.clip_id === clipId ? { ...c, ...updates } : c,
      ),
    })),

  removeClip: (clipId) =>
    set((s) => ({
      ...pushHistory(s),
      clips: s.clips.filter((c) => c.clip_id !== clipId),
      selectedClipId:
        s.selectedClipId === clipId ? null : s.selectedClipId,
    })),

  reorderClips: (fromIndex, toIndex) =>
    set((s) => {
      const clips = [...s.clips];
      const [moved] = clips.splice(fromIndex, 1);
      clips.splice(toIndex, 0, moved);
      let t = 0;
      for (const c of clips) {
        c.timeline_start = Math.round(t * 1000) / 1000;
        if (c.layout && c.layout !== "single" && c.sub_sources?.length > 0) {
          t += Math.min(...c.sub_sources.map((s) => s.end_time - s.start_time));
        } else {
          t += c.end_time - c.start_time;
        }
      }
      return { ...pushHistory(s), clips };
    }),

  replaceClip: (clipId, newClip) =>
    set((s) => ({
      ...pushHistory(s),
      clips: s.clips.map((c) =>
        c.clip_id === clipId ? { ...c, ...newClip } : c,
      ),
    })),

  updateOverlay: (overlayId, updates) =>
    set((s) => ({
      ...pushHistory(s),
      overlays: s.overlays.map((o) =>
        o.overlay_id === overlayId ? { ...o, ...updates } : o,
      ),
    })),

  removeOverlay: (overlayId) =>
    set((s) => ({
      ...pushHistory(s),
      overlays: s.overlays.filter((o) => o.overlay_id !== overlayId),
    })),

  addOverlay: (overlay) =>
    set((s) => ({
      ...pushHistory(s),
      overlays: [...s.overlays, overlay],
    })),

  undo: () =>
    set((s) => {
      if (s._past.length === 0) return s;
      const past = [...s._past];
      const prev = past.pop()!;
      return {
        ...prev,
        _past: past,
        _future: [snap(s), ...s._future].slice(0, MAX_HISTORY),
      };
    }),

  redo: () =>
    set((s) => {
      if (s._future.length === 0) return s;
      const future = [...s._future];
      const next = future.shift()!;
      return {
        ...next,
        _past: [...s._past, snap(s)].slice(-MAX_HISTORY),
        _future: future,
      };
    }),

  canUndo: () => get()._past.length > 0,
  canRedo: () => get()._future.length > 0,

  reset: () =>
    set({
      clips: [],
      overlays: [],
      selectedClipId: null,
      _past: [],
      _future: [],
    }),
}));
