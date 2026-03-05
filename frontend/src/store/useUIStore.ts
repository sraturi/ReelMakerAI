import { create } from "zustand";
import type { Step } from "../types";

interface UIState {
  step: Step;
  loading: boolean;
  loadingMessage: string;
  logs: string[];
  error: string | null;
  activeJobId: string | null;
  renderOutput: string | null;

  setStep: (step: Step) => void;
  setLoading: (loading: boolean, message?: string) => void;
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
  logs: [],
  error: null,
  activeJobId: null,
  renderOutput: null,

  setStep: (step) => set({ step, error: null }),
  setLoading: (loading, message = "") =>
    set({ loading, loadingMessage: message }),
  addLog: (log) => set((s) => ({ logs: [...s.logs, log] })),
  clearLogs: () => set({ logs: [] }),
  setError: (error) => set({ error, loading: false }),
  setActiveJobId: (id) => set({ activeJobId: id }),
  setRenderOutput: (url) => set({ renderOutput: url }),
}));
