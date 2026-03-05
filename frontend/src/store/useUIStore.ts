import { create } from "zustand";
import type { Step } from "../types";

type Theme = "dark" | "light";

interface UIState {
  step: Step;
  theme: Theme;
  loading: boolean;
  loadingMessage: string;
  uploadProgress: number | null;
  logs: string[];
  error: string | null;
  activeJobId: string | null;
  renderOutput: string | null;
  cancelJob: (() => void) | null;

  setStep: (step: Step) => void;
  toggleTheme: () => void;
  setLoading: (loading: boolean, message?: string) => void;
  setUploadProgress: (pct: number | null) => void;
  addLog: (log: string) => void;
  clearLogs: () => void;
  setError: (error: string | null) => void;
  setActiveJobId: (id: string | null) => void;
  setRenderOutput: (url: string | null) => void;
  setCancelJob: (handler: (() => void) | null) => void;
}

function getInitialTheme(): Theme {
  if (typeof window !== "undefined") {
    const saved = localStorage.getItem("theme");
    if (saved === "light" || saved === "dark") return saved;
  }
  return "dark";
}

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("light", theme === "light");
  localStorage.setItem("theme", theme);
}

// Apply on load
const initialTheme = getInitialTheme();
applyTheme(initialTheme);

export const useUIStore = create<UIState>((set) => ({
  step: "upload",
  theme: initialTheme,
  loading: false,
  loadingMessage: "",
  uploadProgress: null,
  logs: [],
  error: null,
  activeJobId: null,
  renderOutput: null,
  cancelJob: null,

  setStep: (step) => set({ step, error: null }),
  toggleTheme: () =>
    set((s) => {
      const next = s.theme === "dark" ? "light" : "dark";
      applyTheme(next);
      return { theme: next };
    }),
  setLoading: (loading, message = "") =>
    set(loading ? { loading, loadingMessage: message } : { loading, loadingMessage: message, cancelJob: null }),
  setUploadProgress: (pct) => set({ uploadProgress: pct }),
  addLog: (log) => set((s) => ({ logs: [...s.logs, log] })),
  clearLogs: () => set({ logs: [] }),
  setError: (error) => set({ error, loading: false, uploadProgress: null, cancelJob: null }),
  setActiveJobId: (id) => set({ activeJobId: id }),
  setRenderOutput: (url) => set({ renderOutput: url }),
  setCancelJob: (handler) => set({ cancelJob: handler }),
}));
