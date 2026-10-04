"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useSession } from "@/components/session";
import { Card, Icon, LabelPill, LinkButton, Loading, Notice, PageHeader } from "@/components/ui";
import { api, fmtDate, urls, type Dashboard } from "@/lib/api";

export default function DashboardPage() {
  const { user } = useSession();
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api.dashboard().then(setData).catch((e) => setError(e.message)); }, []);

  return (
    <>
      <PageHeader title={`Welcome, ${user.display_name}`} subtitle="Your screening activity at a glance."
        action={<LinkButton href="/scan/new"><Icon name="plus" className="h-4 w-4" /> New scan</LinkButton>} />
      {error && <Notice tone="error">{error}</Notice>}
      {!data && !error && <Loading />}
      {data && (
        <div className="space-y-8">
          <div className="grid gap-4 sm:grid-cols-3">
            <Stat label="Your patients" value={data.patients} href="/patients" />
            <Stat label="Your screenings" value={data.scans} />
            <Stat label="Flagged likely PNEUMONIA (recent)" value={data.recent.filter((s) => s.predicted_label === "PNEUMONIA").length}
              hint={`of the last ${data.recent.length}`} />
          </div>

          <Card>
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <h2 className="font-semibold text-ink">Recent screenings</h2>
              <Link href="/patients" className="text-sm font-medium text-brand-700 hover:underline">All patients →</Link>
            </div>
            {data.recent.length === 0 ? (
              <div className="px-5 py-12 text-center text-sm text-muted">
                No screenings yet. <Link className="font-medium text-brand-700 hover:underline" href="/scan/new">Start a new scan</Link>.
              </div>
            ) : (
              <ul className="divide-y divide-slate-100">
                {data.recent.map((s) => (
                  <li key={s.id}>
                    <Link href={`/scans/${s.id}`} className="flex items-center gap-4 px-5 py-3 transition hover:bg-slate-50">
                      {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API image */}
                      <img src={urls.image(s.id, true)} alt="" className="h-12 w-12 rounded-lg bg-slate-900 object-cover" />
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium text-ink">{s.patient_name}</div>
                        <div className="text-xs text-muted">{fmtDate(s.created_at)}</div>
                      </div>
                      <div className="hidden text-right text-sm sm:block">
                        <div className="text-ink">{Math.round(s.confidence * 100)}% confidence</div>
                        <div className="text-xs text-muted">threshold {s.threshold_used.toFixed(2)}</div>
                      </div>
                      <LabelPill label={s.predicted_label} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
    </>
  );
}

function Stat({ label, value, hint, href }: { label: string; value: number; hint?: string; href?: string }) {
  const inner = (
    <Card className="p-5 transition hover:border-brand-200">
      <div className="text-sm text-muted">{label}</div>
      <div className="mt-1 text-3xl font-bold text-ink">{value}</div>
      {hint && <div className="text-xs text-muted">{hint}</div>}
    </Card>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}
