"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Button, Notice, Spinner } from "@/components/ui";

/** In-app confirmation for destructive actions (never the browser's confirm()). */
export function ConfirmDialog({ open, title, children, confirmLabel, onConfirm, onClose }: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work. Nothing was deleted.");
      setBusy(false);
    }
  }

  return (
    <dialog ref={ref} onClose={() => { if (!busy) { setError(null); onClose(); } }}
      onCancel={(e) => { if (busy) e.preventDefault(); }}
      className="m-auto w-[min(92vw,440px)] rounded-2xl border border-slate-200 p-0 shadow-xl backdrop:bg-slate-900/40">
      <div className="space-y-4 p-6">
        <h2 className="text-lg font-semibold text-ink">{title}</h2>
        <div className="space-y-2 text-sm text-slate-700">{children}</div>
        {error && <Notice tone="error">{error}</Notice>}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={() => ref.current?.close()} disabled={busy}>Cancel</Button>
          <Button variant="danger" onClick={confirm} disabled={busy} autoFocus={false}>
            {busy && <Spinner />} {confirmLabel}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
