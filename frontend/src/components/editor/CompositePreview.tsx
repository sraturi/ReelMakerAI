import type { SubSource } from "../../types";

const LAYOUT_CLASSES: Record<string, string> = {
  split_v: "grid-cols-1 grid-rows-2",
  split_h: "grid-cols-2 grid-rows-1",
  pip: "",
  grid: "grid-cols-2 grid-rows-2",
};

interface Props {
  layout: string;
  subSources: SubSource[];
  className?: string;
}

export function CompositePreview({ layout, subSources, className = "" }: Props) {
  if (layout === "pip") {
    return (
      <div className={`relative overflow-hidden rounded ${className}`}>
        {subSources[0] && (
          <img
            src={subSources[0].thumbnail_url}
            alt="main"
            className="h-full w-full object-cover"
          />
        )}
        {subSources[1] && (
          <img
            src={subSources[1].thumbnail_url}
            alt="overlay"
            className="absolute bottom-1 right-1 h-1/3 w-1/3 rounded-sm border-2 border-white object-cover shadow"
          />
        )}
      </div>
    );
  }

  const gridClass = LAYOUT_CLASSES[layout] || "grid-cols-1";

  return (
    <div className={`grid gap-[2px] overflow-hidden rounded bg-white ${gridClass} ${className}`}>
      {subSources.map((sub, i) => (
        <img
          key={i}
          src={sub.thumbnail_url}
          alt={sub.position}
          className="h-full w-full object-cover"
        />
      ))}
    </div>
  );
}
