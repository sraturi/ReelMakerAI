import { useState } from "react";
import { Sparkles, Loader2 } from "lucide-react";
import { useSessionStore } from "../../store/useSessionStore";
import { enhancePrompt } from "../../api/enhance";

const STYLES = [
  { value: "montage", label: "Montage" },
  { value: "travel", label: "Travel" },
  { value: "vlog", label: "Vlog" },
  { value: "tutorial", label: "Tutorial" },
  { value: "aesthetic", label: "Aesthetic" },
  { value: "promo", label: "Promo" },
];

const APPROACHES = [
  { value: "hook", label: "Hook-first" },
  { value: "story", label: "Story / Chronological" },
];

const DURATIONS = [10, 15, 20, 30, 40, 45];

const TRANSITIONS = [
  { value: "auto", label: "Auto" },
  { value: "smooth", label: "Smooth" },
  { value: "dynamic", label: "Dynamic" },
  { value: "dramatic", label: "Dramatic" },
  { value: "cut", label: "Hard Cut" },
];

const MODELS = [
  { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
  { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro" },
];

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string | number;
  options: { value: string | number; label: string }[];
  onChange: (val: string) => void;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-text-muted">
        {label}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-border bg-surface-light px-3 py-2 text-sm text-text outline-none focus:border-primary"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export function SettingsPanel({ sessionId }: { sessionId?: string | null }) {
  const settings = useSessionStore((s) => s.settings);
  const update = useSessionStore((s) => s.updateSettings);
  const [enhancing, setEnhancing] = useState(false);

  async function handleEnhance() {
    if (!settings.prompt.trim() || enhancing) return;
    setEnhancing(true);
    try {
      const enhanced = await enhancePrompt(settings.prompt, settings, sessionId ?? undefined);
      update({ prompt: enhanced });
    } catch {
      // silently fail — user can retry
    }
    setEnhancing(false);
  }

  return (
    <div className="space-y-4 rounded-xl bg-surface p-5">
      <h3 className="text-sm font-semibold">Reel Settings</h3>

      {/* Grid of options */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Select
          label="Style"
          value={settings.reel_style}
          options={STYLES}
          onChange={(v) => update({ reel_style: v })}
        />
        <Select
          label="Approach"
          value={settings.reel_approach}
          options={APPROACHES}
          onChange={(v) => update({ reel_approach: v })}
        />
        <Select
          label="Duration"
          value={settings.target_duration}
          options={DURATIONS.map((d) => ({ value: d, label: `${d}s` }))}
          onChange={(v) => update({ target_duration: parseInt(v) })}
        />
        <Select
          label="Transitions"
          value={settings.transition_style}
          options={TRANSITIONS}
          onChange={(v) => update({ transition_style: v })}
        />
        <Select
          label="Model"
          value={settings.gemini_model}
          options={MODELS}
          onChange={(v) => update({ gemini_model: v })}
        />
        <div>
          <label className="mb-1 block text-xs font-medium text-text-muted">
            BPM
          </label>
          <input
            type="number"
            min={60}
            max={200}
            value={settings.bpm}
            onChange={(e) => update({ bpm: parseInt(e.target.value) || 120 })}
            className="w-full rounded-lg border border-border bg-surface-light px-3 py-2 text-sm text-text outline-none focus:border-primary"
          />
        </div>
      </div>

      {/* Toggles */}
      <div className="flex gap-6">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={settings.captions}
            onChange={(e) => update({ captions: e.target.checked })}
            className="accent-primary"
          />
          Captions
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            name="audio"
            checked={settings.audio_mode === "voice"}
            onChange={() => update({ audio_mode: "voice" })}
            className="accent-primary"
          />
          Voice Only
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            name="audio"
            checked={settings.audio_mode === "original"}
            onChange={() => update({ audio_mode: "original" })}
            className="accent-primary"
          />
          Original Audio
        </label>
      </div>

      {/* Composite layouts */}
      <div>
        <label className="mb-1.5 block text-xs font-medium text-text-muted">
          Composite Layouts (AI may add 0–2 per reel)
        </label>
        <div className="flex flex-wrap gap-x-5 gap-y-1.5">
          {([
            { value: "split_v", label: "Top / Bottom" },
            { value: "split_h", label: "Left / Right" },
            { value: "pip", label: "Picture-in-Picture" },
            { value: "grid", label: "2\u00d72 Grid" },
          ] as const).map(({ value: v, label }) => {
            const checked = (settings.composite_layouts ?? []).includes(v);
            return (
              <label key={v} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => {
                    const cur = settings.composite_layouts ?? [];
                    update({
                      composite_layouts: checked
                        ? cur.filter((l) => l !== v)
                        : [...cur, v],
                    });
                  }}
                  className="accent-primary"
                />
                {label}
              </label>
            );
          })}
        </div>
      </div>

      {/* Prompt — last so user sets preferences first, then AI can use them */}
      <div>
        <div className="mb-1 flex items-center justify-between">
          <label className="block text-xs font-medium text-text-muted">
            Prompt / Direction
          </label>
          <button
            onClick={handleEnhance}
            disabled={!settings.prompt.trim() || enhancing}
            className="flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium text-primary hover:bg-primary/10 disabled:opacity-40"
          >
            {enhancing ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <Sparkles size={12} />
            )}
            {enhancing ? "Enhancing..." : "Enhance Prompt"}
          </button>
        </div>
        <textarea
          value={settings.prompt}
          onChange={(e) => update({ prompt: e.target.value })}
          disabled={enhancing}
          placeholder="e.g. Promote my eyelashes course, make it exciting and professional"
          rows={3}
          className="w-full resize-none rounded-lg border border-border bg-surface-light px-3 py-2 text-sm text-text outline-none placeholder:text-text-muted/50 focus:border-primary disabled:cursor-not-allowed disabled:opacity-50"
        />
      </div>
    </div>
  );
}
