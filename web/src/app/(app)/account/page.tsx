"use client";

import { type FormEvent, useState } from "react";
import { useSession } from "@/components/session";
import { Button, Card, Field, Notice, PageHeader, Spinner, inputCls } from "@/components/ui";
import { api } from "@/lib/api";

export default function AccountPage() {
  const { user } = useSession();
  const [f, setF] = useState({ current: "", next: "", confirm: "" });
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setDone(false);
    if (f.next !== f.confirm) return setError("New passwords do not match.");
    setBusy(true);
    try {
      await api.changePassword(f.current, f.next);
      setDone(true);
      setF({ current: "", next: "", confirm: "" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change the password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Account" subtitle="Your clinician account details and password." />
      <div className="grid max-w-4xl gap-6 lg:grid-cols-[1fr_1.4fr]">
        <Card className="h-fit p-6">
          <h2 className="font-semibold text-ink">Profile</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div><dt className="text-muted">Name</dt><dd className="font-medium text-ink">{user.full_name || "—"}</dd></div>
            <div><dt className="text-muted">Username</dt><dd className="font-medium text-ink">{user.username}</dd></div>
          </dl>
        </Card>

        <Card className="p-6">
          <h2 className="font-semibold text-ink">Change password</h2>
          <p className="mt-1 text-sm text-muted">
            For security, changing your password signs you out on every other device. You stay signed in here.
          </p>
          <form onSubmit={submit} className="mt-5 space-y-4">
            <Field label="Current password">
              <input type="password" className={inputCls} value={f.current} onChange={set("current")} autoComplete="current-password" required />
            </Field>
            <Field label="New password" hint="At least 8 characters.">
              <input type="password" className={inputCls} value={f.next} onChange={set("next")} autoComplete="new-password" required minLength={8} />
            </Field>
            <Field label="Confirm new password">
              <input type="password" className={inputCls} value={f.confirm} onChange={set("confirm")} autoComplete="new-password" required />
            </Field>
            {error && <Notice tone="error">{error}</Notice>}
            {done && <Notice tone="success">Password changed. Other devices have been signed out.</Notice>}
            <div className="flex justify-end">
              <Button type="submit" disabled={busy}>{busy && <Spinner />} Change password</Button>
            </div>
          </form>
        </Card>
      </div>
    </>
  );
}
