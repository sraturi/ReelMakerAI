import { Upload, Search, Edit3, Play, Check } from "lucide-react";
import { useUIStore } from "../../store/useUIStore";
import type { Step } from "../../types";

const steps: { key: Step; label: string; icon: typeof Upload }[] = [
  { key: "upload", label: "Upload", icon: Upload },
  { key: "analyze", label: "Analyze", icon: Search },
  { key: "edit", label: "Edit", icon: Edit3 },
  { key: "render", label: "Render", icon: Play },
  { key: "preview", label: "Preview", icon: Check },
];

const stepOrder: Step[] = ["upload", "analyze", "edit", "render", "preview"];

export function StepIndicator() {
  const currentStep = useUIStore((s) => s.step);
  const currentIdx = stepOrder.indexOf(currentStep);

  return (
    <div className="flex items-center gap-1">
      {steps.map((s, i) => {
        const Icon = s.icon;
        const isActive = s.key === currentStep;
        const isPast = i < currentIdx;

        return (
          <div key={s.key} className="flex items-center">
            <div
              className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                isActive
                  ? "bg-primary text-white"
                  : isPast
                    ? "bg-primary/20 text-primary"
                    : "text-text-muted"
              }`}
            >
              <Icon size={14} />
              <span className="hidden sm:inline">{s.label}</span>
            </div>
            {i < steps.length - 1 && (
              <div
                className={`mx-1 h-px w-4 ${
                  i < currentIdx ? "bg-primary" : "bg-border"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
