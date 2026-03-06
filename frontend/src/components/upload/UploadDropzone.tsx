import { useCallback, useState } from "react";
import { Upload, FileVideo } from "lucide-react";

interface Props {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
}

const VIDEO_TYPES = [
  "video/mp4",
  "video/quicktime",
  "video/x-msvideo",
  "video/x-matroska",
  "video/webm",
];

export function UploadDropzone({ onFiles, disabled }: Props) {
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const files = Array.from(e.dataTransfer.files).filter((f) =>
        VIDEO_TYPES.includes(f.type),
      );
      if (files.length > 0) onFiles(files);
    },
    [onFiles],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || []);
      if (files.length > 0) onFiles(files);
    },
    [onFiles],
  );

  return (
    <label
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 transition-colors sm:p-12 ${
        dragging
          ? "border-primary bg-primary/10"
          : "border-border hover:border-primary/50 hover:bg-surface-light"
      } ${disabled ? "pointer-events-none opacity-50" : ""}`}
    >
      <div className="mb-4 rounded-full bg-primary/10 p-4">
        {dragging ? (
          <FileVideo className="text-primary" size={32} />
        ) : (
          <Upload className="text-primary" size={32} />
        )}
      </div>
      <p className="mb-1 text-base font-medium">
        {dragging ? "Drop videos here" : "Drag & drop videos here"}
      </p>
      <p className="text-sm text-text-muted">
        or click to browse. MP4, MOV, AVI, MKV, WebM
      </p>
      <input
        type="file"
        multiple
        accept="video/*"
        onChange={handleChange}
        className="hidden"
        disabled={disabled}
      />
    </label>
  );
}
