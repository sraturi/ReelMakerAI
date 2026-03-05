import { create } from "zustand";
import type {
  EditingPlan,
  SceneAnalysisResult,
  SessionSettings,
  VideoInfo,
} from "../types";

interface SessionState {
  sessionId: string | null;
  videos: VideoInfo[];
  analysis: SceneAnalysisResult | null;
  plan: EditingPlan | null;
  settings: SessionSettings;

  setSessionId: (id: string) => void;
  setVideos: (videos: VideoInfo[]) => void;
  setAnalysis: (analysis: SceneAnalysisResult) => void;
  setPlan: (plan: EditingPlan) => void;
  updateSettings: (partial: Partial<SessionSettings>) => void;
  reset: () => void;
}

const defaultSettings: SessionSettings = {
  prompt: "",
  reel_style: "montage",
  reel_approach: "hook",
  target_duration: 30,
  bpm: 120,
  captions: true,
  audio_mode: "voice",
  transition_style: "auto",
  gemini_model: "gemini-2.5-flash",
};

export const useSessionStore = create<SessionState>((set) => ({
  sessionId: null,
  videos: [],
  analysis: null,
  plan: null,
  settings: { ...defaultSettings },

  setSessionId: (id) => set({ sessionId: id }),
  setVideos: (videos) => set({ videos }),
  setAnalysis: (analysis) => set({ analysis }),
  setPlan: (plan) => set({ plan }),
  updateSettings: (partial) =>
    set((s) => ({ settings: { ...s.settings, ...partial } })),
  reset: () =>
    set({
      sessionId: null,
      videos: [],
      analysis: null,
      plan: null,
      settings: { ...defaultSettings },
    }),
}));
