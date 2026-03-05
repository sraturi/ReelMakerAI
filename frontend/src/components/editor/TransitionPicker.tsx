const TRANSITIONS = [
  "fade",
  "fadeblack",
  "dissolve",
  "wipeleft",
  "wiperight",
  "slideup",
  "slideleft",
  "circleopen",
  "radial",
];

interface Props {
  value: string;
  onChange: (val: string) => void;
}

export function TransitionPicker({ value, onChange }: Props) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-text-muted">
        Transition
      </label>
      <div className="flex flex-wrap gap-1.5">
        {TRANSITIONS.map((t) => (
          <button
            key={t}
            onClick={() => onChange(t)}
            className={`rounded-md px-2 py-1 text-xs font-medium transition-colors ${
              value === t
                ? "bg-primary text-white"
                : "bg-surface-lighter text-text-muted hover:text-text"
            }`}
          >
            {t}
          </button>
        ))}
      </div>
    </div>
  );
}
