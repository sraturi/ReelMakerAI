import {
  Columns2,
  Grid2x2,
  Layers,
  Rows2,
  Square,
} from "lucide-react";

const LAYOUTS = [
  { value: "single", label: "Single", icon: Square },
  { value: "split_v", label: "Top/Bottom", icon: Rows2 },
  { value: "split_h", label: "Left/Right", icon: Columns2 },
  { value: "pip", label: "PiP", icon: Layers },
  { value: "grid", label: "Grid", icon: Grid2x2 },
] as const;

interface Props {
  value: string;
  onChange: (layout: string) => void;
}

export function LayoutPicker({ value, onChange }: Props) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-text-muted">
        Layout
      </label>
      <div className="flex flex-wrap gap-1.5">
        {LAYOUTS.map(({ value: v, label, icon: Icon }) => (
          <button
            key={v}
            onClick={() => onChange(v)}
            className={`flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
              value === v
                ? "bg-primary/20 text-primary"
                : "bg-surface-lighter text-text-muted hover:text-text"
            }`}
          >
            <Icon size={12} />
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
