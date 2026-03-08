import { Upload, Search, MessageSquare, Edit3, Play, Check } from "lucide-react";
import { useUIStore } from "../../store/useUIStore";
import type { Step } from "../../types";

const steps: { key: Step; label: string; icon: typeof Upload }[] = [
  { key: "upload", label: "Upload", icon: Upload },
  { key: "analyze", label: "Analyze", icon: Search },
  { key: "prompt", label: "Prompt", icon: MessageSquare },
  { key: "edit", label: "Edit", icon: Edit3 },
  { key: "render", label: "Render", icon: Play },
  { key: "preview", label: "Preview", icon: Check },
];

const stepOrder: Step[] = ["upload", "analyze", "prompt", "edit", "render", "preview"];

// Steps users can navigate back to (skip analyze/render — they're transient)
const navigableSteps = new Set<Step>(["upload", "prompt", "edit", "preview"]);

export function StepIndicator() {
  const currentStep = useUIStore((s) => s.step);
  const setStep = useUIStore((s) => s.setStep);
  if (currentStep === "home") return null;
  const currentIdx = stepOrder.indexOf(currentStep);
  const activeStep = steps[currentIdx];
  const ActiveIcon = activeStep?.icon;

  return (
    <>
      {/* Mobile: compact pill with active step only */}
      {activeStep && (
        <div className="flex items-center gap-1.5 rounded-full gradient-bg px-3 py-1.5 text-xs font-medium text-white sm:hidden">
          <ActiveIcon size={14} />
          <span>{activeStep.label}</span>
          <span className="ml-0.5 opacity-70">{currentIdx + 1}/{steps.length}</span>
        </div>
      )}

      {/* Desktop: full step indicator */}
      <div className="hidden sm:flex items-center gap-1">
        {steps.map((s, i) => {
          const Icon = s.icon;
          const isActive = s.key === currentStep;
          const isPast = i < currentIdx;
          const canClick = isPast && navigableSteps.has(s.key);

          return (
            <div key={s.key} className="flex items-center">
              <button
                type="button"
                disabled={!canClick}
                onClick={() => canClick && setStep(s.key)}
                className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                  isActive
                    ? "gradient-bg text-white"
                    : isPast
                      ? "bg-primary/20 text-primary hover:bg-primary/30 cursor-pointer"
                      : "text-text-muted cursor-default"
                } ${!canClick && !isActive ? "cursor-default" : ""}`}
              >
                <Icon size={14} />
                <span>{s.label}</span>
              </button>
              {i < steps.length - 1 && (
                <div
                  className={`mx-1 h-px w-4 ${
                    i < currentIdx ? "gradient-bg" : "bg-border"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}
