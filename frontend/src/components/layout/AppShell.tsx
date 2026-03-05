import { Film, Sun, Moon } from "lucide-react";
import { StepIndicator } from "./StepIndicator";
import { useUIStore } from "../../store/useUIStore";
import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
}

export function AppShell({ children }: Props) {
  const theme = useUIStore((s) => s.theme);
  const toggleTheme = useUIStore((s) => s.toggleTheme);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-border bg-surface/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <Film className="text-primary" size={24} />
            <span className="gradient-text text-lg font-bold">ReelMaker AI</span>
          </div>
          <div className="flex items-center gap-3">
            <StepIndicator />
            <button
              onClick={toggleTheme}
              className="rounded-lg p-2 text-text-muted transition-colors hover:bg-surface-light hover:text-text"
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        {children}
      </main>
    </div>
  );
}
