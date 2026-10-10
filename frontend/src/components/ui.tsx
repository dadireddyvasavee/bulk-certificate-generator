import { useState, type ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { download } from "../services/api";
export function Badge({ status }: { status: string }) {
  return (
    <span className={"badge " + status}>{status.replaceAll("_", " ")}</span>
  );
}
export function Progress({ value }: { value: number }) {
  return (
    <div className="progress-wrap">
      <progress aria-label="Job progress" max={100} value={value} />
      <span>{value}%</span>
    </div>
  );
}
export function ErrorBox({ error }: { error: unknown }) {
  return error ? (
    <p role="alert" className="error">
      {error instanceof Error ? error.message : String(error)}
    </p>
  ) : null;
}
export function Loading() {
  return (
    <p role="status" className="loading">
      Loading records…
    </p>
  );
}
export function Pager({
  page,
  total,
  size,
  onChange,
}: {
  page: number;
  total: number;
  size: number;
  onChange: (page: number) => void;
}) {
  return (
    <div className="pager">
      <button disabled={page === 1} onClick={() => onChange(page - 1)}>
        Previous
      </button>
      <span>
        Page {page} of {Math.max(1, Math.ceil(total / size))}
      </span>
      <button
        disabled={page * size >= total}
        onClick={() => onChange(page + 1)}
      >
        Next
      </button>
    </div>
  );
}
export function DownloadButton({
  path,
  filename,
  children,
}: {
  path: string;
  filename: string;
  children: ReactNode;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  return (
    <>
      <button
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            await download(path, filename);
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Downloading…" : children}
      </button>
      <ErrorBox error={error} />
    </>
  );
}
export function Confirm({
  open,
  onClose,
  onConfirm,
  busy,
  children,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  busy: boolean;
  children: ReactNode;
}) {
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(v) => {
        if (!v && !busy) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content className="dialog">
          <Dialog.Title>Confirm certificate batch</Dialog.Title>
          <Dialog.Description>
            Review the batch before creating a persistent generation job.
          </Dialog.Description>
          {children}
          <div className="actions">
            <button disabled={busy} onClick={onClose}>
              Back to editing
            </button>
            <button className="primary" disabled={busy} onClick={onConfirm}>
              {busy ? "Submitting…" : "Generate certificates"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
