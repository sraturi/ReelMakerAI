import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { ClipCard } from "./ClipCard";
import { useEditorStore } from "../../store/useEditorStore";

interface Props {
  onSuggest: (clipIndex: number) => void;
}

export function ClipCardList({ onSuggest }: Props) {
  const clips = useEditorStore((s) => s.clips);
  const selectedClipId = useEditorStore((s) => s.selectedClipId);
  const selectClip = useEditorStore((s) => s.selectClip);
  const removeClip = useEditorStore((s) => s.removeClip);
  const reorderClips = useEditorStore((s) => s.reorderClips);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const fromIndex = clips.findIndex((c) => c.clip_id === active.id);
    const toIndex = clips.findIndex((c) => c.clip_id === over.id);
    if (fromIndex !== -1 && toIndex !== -1) {
      reorderClips(fromIndex, toIndex);
    }
  }

  if (clips.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-border text-sm text-text-muted">
        No clips in plan
      </div>
    );
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={clips.map((c) => c.clip_id)}
        strategy={verticalListSortingStrategy}
      >
        <div className="space-y-2">
          {clips.map((clip, i) => (
            <ClipCard
              key={clip.clip_id}
              clip={clip}
              index={i}
              isSelected={clip.clip_id === selectedClipId}
              onSelect={() => selectClip(clip.clip_id)}
              onRemove={() => removeClip(clip.clip_id)}
              onSuggest={() => onSuggest(i)}
            />
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
}
