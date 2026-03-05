import { useState } from "react";
import { ImageOff } from "lucide-react";

interface Props {
  src: string;
  alt?: string;
  className?: string;
}

export function ThumbnailImage({ src, alt = "", className = "" }: Props) {
  const [error, setError] = useState(false);

  if (!src || error) {
    return (
      <div
        className={`flex items-center justify-center bg-surface-lighter text-text-muted ${className}`}
      >
        <ImageOff size={24} />
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      className={`object-cover ${className}`}
      onError={() => setError(true)}
    />
  );
}
