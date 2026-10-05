"use client";

import { type FormEvent, useState } from "react";
import { Button, Field, Notice, Spinner, inputCls } from "@/components/ui";
import { api, type Patient } from "@/lib/api";

/** Add a patient, or edit one when `patient` is given. */
export function PatientForm({ patient, onSaved, onCancel }: {
  patient?: Patient;
  onSaved: (p: Patient) => void;
  onCancel?: () => void;
}) {
  const [f, setF] = useState({
    name: patient?.name ?? "",
    age: patient?.age != null ? String(patient.age) : "",
    sex: patient?.sex ?? "",
    note: patient?.note ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const body = { name: f.name, age: f.age === "" ? null : Number(f.age), sex: f.sex || null, note: f.note || null };
    try {
      onSaved(patient ? await api.updatePatient(patient.id, body) : await api.createPatient(body));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the patient.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <Field label="Name" hint="Use fake/sample names during development.">
        <input className={inputCls} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required maxLength={128} autoFocus />
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Age">
          <input type="number" min={0} max={130} className={inputCls} value={f.age} onChange={(e) => setF({ ...f, age: e.target.value })} />
        </Field>
        <Field label="Sex">
          <select className={inputCls} value={f.sex} onChange={(e) => setF({ ...f, sex: e.target.value })}>
            <option value="">—</option><option>Female</option><option>Male</option><option>Other</option>
          </select>
        </Field>
      </div>
      <Field label="Note (optional)">
        <textarea rows={2} className={inputCls} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} maxLength={2000} />
      </Field>
      {error && <Notice tone="error">{error}</Notice>}
      <div className="flex justify-end gap-2">
        {onCancel && <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>}
        <Button type="submit" disabled={busy}>{busy && <Spinner />} {patient ? "Save changes" : "Add patient"}</Button>
      </div>
    </form>
  );
}
