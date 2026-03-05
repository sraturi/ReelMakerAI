interface Props {
  open: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  message,
  onConfirm,
  onCancel,
}: Props) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-xl bg-surface p-6 shadow-2xl">
        <h3 className="mb-2 text-lg font-semibold">{title}</h3>
        <p className="mb-6 text-sm text-text-muted">{message}</p>
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="rounded-lg px-4 py-2 text-sm text-text-muted hover:bg-surface-lighter"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="rounded-lg bg-error px-4 py-2 text-sm font-medium text-white hover:bg-error/80"
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}
