const EFFECTS = [
  { value: "none", label: "None" },
  { value: "zoom_in", label: "Zoom In" },
  { value: "zoom_out", label: "Zoom Out" },
  { value: "pan_left", label: "Pan Left" },
  { value: "pan_right", label: "Pan Right" },
];

interface Props {
  value: string;
  onChange: (val: string) => void;
}

export function KenBurnsPicker({ value, onChange }: Props) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-text-muted">
        Ken Burns
      </label>
      <div className="flex flex-wrap gap-1.5">
        {EFFECTS.map((e) => (
          <button
            key={e.value}
            onClick={() => onChange(e.value)}
            className={`rounded-md px-2 py-1 text-xs font-medium transition-colors ${
              value === e.value
                ? "bg-accent text-black"
                : "bg-surface-lighter text-text-muted hover:text-text"
            }`}
          >
            {e.label}
          </button>
        ))}
      </div>
    </div>
  );
}
