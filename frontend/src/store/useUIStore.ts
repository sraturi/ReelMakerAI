import { create } from "zustand";
import type { Step } from "../types";

interface UIState {
  step: Step;
  loading: boolean;
  loadingMessage: string;
  uploadProgress: number | null;
  logs: string[];
  error: string | null;
  activeJobId: string | null;
  renderOutput: string | null;

  setStep: (step: Step) => void;
  setLoading: (loading: boolean, message?: string) => void;
  setUploadProgress: (pct: number | null) => void;
  addLog: (log: string) => void;
  clearLogs: () => void;
  setError: (error: string | null) => void;
  setActiveJobId: (id: string | null) => void;
  setRenderOutput: (url: string | null) => void;
}

export const useUIStore = create<UIState>((set) => ({
  step: "upload",
  loading: false,
  loadingMessage: "",
  uploadProgress: null,
  logs: [],
  error: null,
  activeJobId: null,
  renderOutput: null,

  setStep: (step) => set({ step, error: null }),
  setLoading: (loading, message = "") =>
    set({ loading, loadingMessage: message }),
  setUploadProgress: (pct) => set({ uploadProgress: pct }),
  addLog: (log) => set((s) => ({ logs: [...s.logs, log] })),
  clearLogs: () => set({ logs: [] }),
  setError: (error) => set({ error, loading: false, uploadProgress: null }),
  setActiveJobId: (id) => set({ activeJobId: id }),
  setRenderOutput: (url) => set({ renderOutput: url }),
}));
