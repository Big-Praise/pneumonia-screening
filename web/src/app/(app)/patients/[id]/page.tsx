"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { PatientForm } from "@/components/patient-form";
import { Button, Card, Icon, LabelPill, LinkButton, Loading, Notice, PageHeader } from "@/components/ui";
import { api, fmtDate, urls, type Patient, type Scan } from "@/lib/api";

export default function PatientHistoryPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<(Patient & { scans: Scan[] }) | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const router = useRouter();

  useEffect(() => { api.patient(Number(id)).then(setData).catch((e) => setError(e.message)); }, [id]);

  if (error) return <Notice tone="error">{error}</Notice>;
  if (!data) return <Loading />;

  const facts = [data.age != null ? `Age ${data.age}` : null, data.sex, `added ${fmtDate(data.created_at)}`].filter(Boolean);

  return (
    <>
      <Link href="/patients" className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline">
        <Icon name="back" className="h-4 w-4" /> All patients
      </Link>
      <PageHeader title={data.name} subtitle={facts.join(" · ")}
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setEditing(true)}><Icon name="edit" className="h-4 w-4" /> Edit</Button>
            <LinkButton href={`/scan/new?patient=${data.id}`}><Icon name="plus" className="h-4 w-4" /> New scan for this patient</LinkButton>
          </div>
        } />
      {editing && (
        <Card className="mb-6 p-5">
          <h2 className="mb-4 font-semibold">Edit patient</h2>
          <PatientForm patient={data} onCancel={() => setEditing(false)}
            onSaved={(p) => { setData({ ...data, ...p }); setEditing(false); }} />
        </Card>
      )}
      {data.note && !editing && <Card className="mb-6 px-5 py-4 text-sm text-slate-700">{data.note}</Card>}

      <h2 className="mb-3 font-semibold text-ink">Scan history ({data.scans.length})</h2>
      {data.scans.length === 0 ? (
        <Card className="px-6 py-12 text-center text-sm text-muted">No scans yet for this patient.</Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.scans.map((s) => (
            <Link key={s.id} href={`/scans/${s.id}`}
              className="group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:border-brand-300 hover:shadow-md">
              <div className="aspect-[4/3] overflow-hidden bg-slate-900">
                {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API image */}
                <img src={urls.image(s.id, true)} alt="Chest X-ray thumbnail" className="h-full w-full object-contain opacity-90 transition group-hover:opacity-100" />
              </div>
              <div className="space-y-2 p-4">
                <div className="flex items-center justify-between gap-2">
                  <LabelPill label={s.predicted_label} />
                  <span className="text-sm font-semibold text-ink">{Math.round(s.confidence * 100)}%</span>
                </div>
                <div className="text-sm text-ink">{fmtDate(s.created_at)}</div>
                <div className="text-xs text-muted">p = {s.pneumonia_prob.toFixed(3)} · threshold {s.threshold_used.toFixed(2)}</div>
              </div>
            </Link>
          ))}
        </div>
      )}

      <div className="mt-12 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-rose-200 bg-rose-50/40 px-5 py-4">
        <div className="text-sm">
          <div className="font-semibold text-ink">Delete this patient</div>
          <div className="text-muted">Permanently removes the patient, all {data.scans.length} scan(s) and their stored X-rays.</div>
        </div>
        <Button variant="danger" onClick={() => setDeleting(true)}><Icon name="trash" className="h-4 w-4" /> Delete patient</Button>
      </div>
      <ConfirmDialog open={deleting} onClose={() => setDeleting(false)}
        title={`Delete ${data.name}?`} confirmLabel="Delete permanently"
        onConfirm={async () => { await api.deletePatient(data.id); router.replace("/patients"); }}>
        <p>This permanently deletes the patient record, <b>{data.scans.length} scan(s)</b>, their X-ray images, explanations and saved thresholds.</p>
        <p>It can&apos;t be undone. Downloaded PDF reports are not affected.</p>
      </ConfirmDialog>
    </>
  );
}
