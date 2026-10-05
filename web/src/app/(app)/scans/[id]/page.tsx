"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { useSession } from "@/components/session";
import { Button, Card, Icon, Loading, Notice, Spinner, cx } from "@/components/ui";
import { api, classify, fmtDate, urls, type Label, type LimeStatus, type ScanDetail } from "@/lib/api";

export default function ScanPage() {
  const { id } = useParams<{ id: string }>();
  const scanId = Number(id);
  const { meta } = useSession();
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [threshold, setThreshold] = useState(0.5);
  const [opacity, setOpacity] = useState(meta.default_opacity);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const router = useRouter();

  useEffect(() => {
    api.scan(scanId).then((s) => { setScan(s); setThreshold(s.threshold_used); }).catch((e) => setError(e.message));
  }, [scanId]);

  if (error) return <Notice tone="error">{error}</Notice>;
  if (!scan) return <Loading label="Loading screening…" />;

  // Sliders are display-only and computed here, instantly: same rule as the backend.
  const { label, confidence } = classify(scan.pneumonia_prob, threshold);
  const unsaved = Math.abs(threshold - scan.threshold_used) > 1e-9;
  const isPn = label === "PNEUMONIA";
  const canExplain = scan.model.status === "ready" || scan.model.status === "demo";

  async function saveThreshold() {
    setSaving(true);
    try {
      const s = await api.saveThreshold(scanId, threshold);
      setScan((prev) => (prev ? { ...prev, ...s } : prev));
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save the threshold.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Link href={`/patients/${scan.patient.id}`} className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline">
        <Icon name="back" className="h-4 w-4" /> {scan.patient.name}&apos;s history
      </Link>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        {/* Result card */}
        <Card className={cx("p-6", isPn ? "border-amber-200 bg-gradient-to-br from-amber-50 to-white" : "border-brand-200 bg-gradient-to-br from-brand-50 to-white")}>
          <div className="text-xs font-semibold uppercase tracking-wider text-muted">Screening result</div>
          <h1 className={cx("mt-1 text-3xl font-bold tracking-tight", isPn ? "text-amber-700" : "text-brand-700")}>
            {isPn ? "Findings suggest pneumonia" : "No pneumonia pattern detected"}
          </h1>
          <p className="mt-2 text-sm text-slate-700">
            Screening result: likely <b>{label}</b> · {scan.patient.name} · {fmtDate(scan.created_at)}
          </p>
          <div className="mt-5">
            <div className="mb-1.5 flex justify-between text-sm">
              <span className="font-medium text-ink">Confidence in this result</span>
              <span className="font-bold text-ink">{Math.round(confidence * 100)}%</span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-slate-200">
              <div className={cx("h-full rounded-full transition-all", isPn ? "bg-amber-500" : "bg-brand-600")} style={{ width: `${confidence * 100}%` }} />
            </div>
          </div>
          {confidence < 0.5 && (
            <div className="mt-4"><Notice tone="warn">The model itself leans the other way here; this label comes from the threshold setting. Treat it as borderline.</Notice></div>
          )}
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <a href={urls.report(scan.id)} className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-brand-700">
              <Icon name="download" className="h-4 w-4" /> Download PDF report
            </a>
            {unsaved && <span className="text-xs text-muted">PDF uses the saved threshold ({scan.threshold_used.toFixed(2)}).</span>}
          </div>
        </Card>

        {/* Threshold */}
        <Card className="p-6">
          <div className="flex items-baseline justify-between">
            <h2 className="font-semibold text-ink">Confidence threshold</h2>
            <span className="font-mono text-lg font-semibold text-ink">{threshold.toFixed(2)}</span>
          </div>
          <input type="range" min={0} max={1} step={0.01} value={threshold} aria-label="Confidence threshold"
            onChange={(e) => setThreshold(Number(e.target.value))} className="mt-3 w-full" />
          <div className="flex justify-between text-[11px] text-muted"><span>more sensitive</span><span>stricter</span></div>
          <p className="mt-3 text-sm text-slate-700">
            Lowering the threshold catches more pneumonia but raises more false alarms; raising it is stricter but misses more cases.
            This changes how the result is <b>displayed</b> — not the model or its probability.
          </p>
          <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
            Model pneumonia probability <b>p = {scan.pneumonia_prob.toFixed(3)}</b> · PNEUMONIA when p ≥ threshold · saved threshold {scan.threshold_used.toFixed(2)}
          </div>
          <div className="mt-4 flex items-center gap-3">
            {unsaved ? (
              <>
                <Button onClick={saveThreshold} disabled={saving}>{saving && <Spinner />} Save threshold</Button>
                <Button variant="secondary" onClick={() => setThreshold(scan.threshold_used)} disabled={saving}>Reset</Button>
              </>
            ) : (
              <span className="flex items-center gap-1.5 text-sm text-emerald-700">
                <Icon name="check" className="h-4 w-4" /> {saved ? "Threshold saved" : "Result saved at this threshold"}
              </span>
            )}
          </div>
        </Card>
      </div>

      {/* Explanations */}
      <section className="mt-8">
        <h2 className="text-xl font-bold text-ink">What drove this result</h2>
        <p className="mt-1 text-sm text-muted">Two independent explanations; agreement increases confidence in the highlighted region.</p>
        <div className="mt-4 grid gap-5 md:grid-cols-3">
          <Panel title="Original X-ray">
            <XrayFrame>
              {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API image */}
              <img src={urls.image(scan.id)} alt="Original chest X-ray" className="w-full" />
            </XrayFrame>
          </Panel>

          <Panel title={`Grad-CAM for “${label}”`} demo={scan.model.status === "demo"}>
            {canExplain ? <GradCam key={label} scanId={scan.id} label={label} opacity={opacity} /> : <Notice tone="warn">The model isn&apos;t loaded, so Grad-CAM can&apos;t be computed right now.</Notice>}
            <label className="mt-3 block">
              <span className="flex justify-between text-sm"><span className="font-medium">Heatmap opacity</span><span className="font-mono">{opacity.toFixed(2)}</span></span>
              <input type="range" min={0} max={1} step={0.05} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} className="w-full" aria-label="Heatmap opacity" />
            </label>
            <p className="text-xs text-muted">Red = regions that most pushed the model towards this result. Coarse 7×7 grid: broad regions, not lesion boundaries.</p>
          </Panel>

          <Panel title={`LIME for “${label}”`} demo={scan.model.status === "demo"}>
            <LimePanel scanId={scan.id} label={label} initial={scan.lime} canRun={canExplain} samples={meta.lime_num_samples} />
          </Panel>
        </div>
        <p className="mt-4 text-xs text-muted">Highlights outside the lungs suggest the model may be using non-clinical cues — interpret with care.</p>
      </section>

      <div className="mt-12 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-rose-200 bg-rose-50/40 px-5 py-4">
        <div className="text-sm">
          <div className="font-semibold text-ink">Delete this scan</div>
          <div className="text-muted">Permanently removes this screening, its X-ray image and its explanations.</div>
        </div>
        <Button variant="danger" onClick={() => setDeleting(true)}><Icon name="trash" className="h-4 w-4" /> Delete scan</Button>
      </div>
      <ConfirmDialog open={deleting} onClose={() => setDeleting(false)}
        title="Delete this scan?" confirmLabel="Delete permanently"
        onConfirm={async () => { await api.deleteScan(scan.id); router.replace(`/patients/${scan.patient.id}`); }}>
        <p>This permanently deletes the screening from <b>{fmtDate(scan.created_at)}</b> for <b>{scan.patient.name}</b>, including the X-ray image, Grad-CAM/LIME results and saved threshold.</p>
        <p>It can&apos;t be undone. Downloaded PDF reports are not affected.</p>
      </ConfirmDialog>
    </>
  );
}

function Panel({ title, demo, children }: { title: string; demo?: boolean; children: React.ReactNode }) {
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        {demo && <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-800">DEMO — meaningless</span>}
      </div>
      {children}
    </Card>
  );
}

function XrayFrame({ children }: { children: React.ReactNode }) {
  return <div className="relative overflow-hidden rounded-xl bg-slate-900">{children}</div>;
}

/** Heatmap image laid over the X-ray; opacity is pure CSS, so the slider is instant. */
function GradCam({ scanId, label, opacity }: { scanId: number; label: Label; opacity: number }) {
  const [state, setState] = useState<"loading" | "ok" | "error">("loading");
  // Parent passes key={label}, so a label flip remounts this and resets to "loading".
  return (
    <XrayFrame>
      {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API image */}
      <img src={urls.image(scanId)} alt="" className="w-full" />
      {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API image */}
      <img src={urls.gradcam(scanId, label)} alt={`Grad-CAM heatmap for ${label}`}
        onLoad={() => setState("ok")} onError={() => setState("error")}
        className="absolute inset-0 h-full w-full transition-opacity" style={{ opacity: state === "ok" ? opacity : 0 }} />
      {state === "loading" && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-900/40 text-sm text-white"><Spinner className="mr-2" /> Computing Grad-CAM…</div>
      )}
      {state === "error" && (
        <div className="absolute inset-x-2 bottom-2"><Notice tone="error">Grad-CAM could not be computed for this image.</Notice></div>
      )}
    </XrayFrame>
  );
}

function LimePanel({ scanId, label, initial, canRun, samples }:
  { scanId: number; label: Label; initial: LimeStatus; canRun: boolean; samples: number }) {
  const [st, setSt] = useState<LimeStatus>(initial);

  const poll = useCallback(() => api.limeStatus(scanId).then(setSt).catch(() => {}), [scanId]);
  useEffect(() => { if (initial.status === "done") poll(); }, [initial.status, poll]); // fetch per-label facts

  // While LIME runs, keep exactly one long-poll open (server holds it up to 20 s).
  // On Cloud Run an open request is what keeps the container's CPU running the job.
  const running = st.status === "queued" || st.status === "running";
  useEffect(() => {
    if (!running) return;
    let alive = true;
    (async () => {
      while (alive) {
        try {
          const next = await api.limeStatus(scanId, 20);
          if (!alive) return;
          setSt(next);
          if (next.status !== "queued" && next.status !== "running") return;
        } catch {
          await new Promise((r) => setTimeout(r, 3000)); // transient error: back off, retry
        }
      }
    })();
    return () => { alive = false; };
  }, [running, scanId]);

  async function start() {
    try { setSt(await api.limeStart(scanId)); } catch { setSt({ status: "error", progress: 0 }); }
  }

  if (st.status === "done") {
    const info = st.labels?.[label];
    const agree = info?.agreement;
    const word = agree == null ? null : agree >= 0.5 ? "high" : agree >= 0.2 ? "partial" : "low";
    return (
      <>
        <XrayFrame>
          {/* eslint-disable-next-line @next/next/no-img-element -- authenticated API image */}
          <img key={label} src={urls.lime(scanId, label)} alt={`LIME regions for ${label}`} className="w-full" />
        </XrayFrame>
        {info && !info.has_regions && <Notice tone="warn">LIME found no region supporting this result.</Notice>}
        {info?.weak && <Notice tone="warn">Weak evidence: hiding any single region barely changes the prediction, so these highlights are only loosely supported.</Notice>}
        {word && (
          <p className="text-sm text-slate-700">Agreement with Grad-CAM: <b>{word}</b> ({Math.round(agree! * 100)}% of LIME&apos;s regions fall in Grad-CAM&apos;s hottest area).</p>
        )}
        <p className="text-xs text-muted">Green = the superpixels whose removal most weakened this result.</p>
      </>
    );
  }

  if (st.status === "queued" || st.status === "running") {
    const pct = Math.round(st.progress * 100);
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 rounded-xl bg-slate-50 px-4 py-14 text-center">
        <Spinner className="h-6 w-6 text-brand-600" />
        <div className="text-sm font-medium text-ink">{st.status === "queued" ? "Queued…" : `Running LIME — ${pct}%`}</div>
        <div className="h-2 w-full max-w-[220px] overflow-hidden rounded-full bg-slate-200">
          <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${Math.max(pct, 3)}%` }} />
        </div>
        <p className="text-xs text-muted">Testing {samples.toLocaleString()} altered copies of the image. You can leave this page; it keeps running.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 rounded-xl bg-slate-50 px-4 py-14 text-center">
      {st.status === "error" && <Notice tone="error">LIME could not be computed for this image.</Notice>}
      <p className="text-sm text-slate-700">LIME re-runs the model on {samples.toLocaleString()} altered copies of the image — about 1–2 minutes. The result is saved, so each scan only runs once.</p>
      <Button onClick={start} disabled={!canRun}>{st.status === "error" ? "Try again" : "Show LIME explanation"}</Button>
    </div>
  );
}
