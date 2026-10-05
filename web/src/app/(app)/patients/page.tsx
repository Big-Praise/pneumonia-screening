"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { PatientForm } from "@/components/patient-form";
import { Button, Card, Icon, Loading, Notice, PageHeader, inputCls } from "@/components/ui";
import { api, fmtDate, type PatientSummary } from "@/lib/api";

export default function PatientsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<PatientSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [q, setQ] = useState("");

  useEffect(() => { api.patients().then(setRows).catch((e) => setError(e.message)); }, []);
  const shown = useMemo(
    () => rows?.filter((p) => p.name.toLowerCase().includes(q.trim().toLowerCase())) ?? [], [rows, q]);

  return (
    <>
      <PageHeader title="Patients" subtitle="Select a patient to see their scan history."
        action={<Button onClick={() => setAdding(true)}><Icon name="plus" className="h-4 w-4" /> Add patient</Button>} />

      {adding && (
        <Card className="mb-6 p-5">
          <h2 className="mb-4 font-semibold">New patient</h2>
          <PatientForm onCancel={() => setAdding(false)} onSaved={(p) => router.push(`/patients/${p.id}`)} />
        </Card>
      )}

      {error && <Notice tone="error">{error}</Notice>}
      {!rows && !error && <Loading />}
      {rows && rows.length === 0 && !adding && (
        <Card className="px-6 py-14 text-center">
          <p className="text-muted">No patients yet.</p>
          <Button className="mt-4" onClick={() => setAdding(true)}><Icon name="plus" className="h-4 w-4" /> Add your first patient</Button>
        </Card>
      )}
      {rows && rows.length > 0 && (
        <Card>
          <div className="border-b border-slate-100 p-4">
            <input className={inputCls + " max-w-xs"} placeholder="Search by name…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-muted">
                <tr className="border-b border-slate-100">
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">Age / sex</th>
                  <th className="px-5 py-3 font-medium">Scans</th>
                  <th className="px-5 py-3 font-medium">Last scan</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {shown.map((p) => (
                  <tr key={p.id} onClick={() => router.push(`/patients/${p.id}`)} className="cursor-pointer transition hover:bg-slate-50">
                    <td className="px-5 py-3.5 font-medium text-ink">
                      <Link href={`/patients/${p.id}`} onClick={(e) => e.stopPropagation()}>{p.name}</Link>
                    </td>
                    <td className="px-5 py-3.5 text-slate-600">{p.age ?? "—"} / {p.sex ?? "—"}</td>
                    <td className="px-5 py-3.5 text-slate-600">{p.scan_count}</td>
                    <td className="px-5 py-3.5 text-slate-600">{p.last_scan_at ? fmtDate(p.last_scan_at) : "—"}</td>
                    <td className="px-5 py-3.5 text-right text-brand-700">View →</td>
                  </tr>
                ))}
                {shown.length === 0 && (
                  <tr><td colSpan={5} className="px-5 py-8 text-center text-muted">No patients match “{q}”.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}
