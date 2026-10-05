"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { PatientForm } from "@/components/patient-form";
import { useSession } from "@/components/session";
import { Button, Card, Field, Icon, Loading, Notice, PageHeader, Spinner, cx, inputCls } from "@/components/ui";
import { api, type PatientSummary } from "@/lib/api";

// Hosting proxies cap request bodies (~4.5 MB on Vercel). Larger images are
// resized client-side; the model only ever sees a 224x224 version anyway.
const UPLOAD_SOFT_LIMIT = 4 * 1024 * 1024;
const RESIZE_MAX_PX = 2048;

export default function NewScanPage() {
  return <Suspense fallback={<Loading />}><NewScan /></Suspense>;
}

function NewScan() {
  const router = useRouter();
  const params = useSearchParams();
  const { meta } = useSession();
  const [patients, setPatients] = useState<PatientSummary[] | null>(null);
  const [patientId, setPatientId] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [resizedNote, setResizedNote] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.patients().then((ps) => {
      setPatients(ps);
      const wanted = Number(params.get("patient"));
      setPatientId(ps.find((p) => p.id === wanted)?.id ?? ps[0]?.id ?? null);
    }).catch((e) => setError(e.message));
  }, [params]);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  function pick(f: File | undefined) {
    setError(null);
    if (!f) return;
    if (!["image/jpeg", "image/png"].includes(f.type)) return setError("Only JPG and PNG images are supported.");
    if (f.size > meta.max_upload_mb * 1024 * 1024) return setError(`File is larger than ${meta.max_upload_mb} MB.`);
    setFile(f);
    setPreview(URL.createObjectURL(f));
  }

  async function analyze() {
    if (!file || patientId == null) return;
    setBusy(true);
    setError(null);
    try {
      let blob: Blob = file;
      let name = file.name;
      if (file.size > UPLOAD_SOFT_LIMIT) {
        blob = await downscale(file, RESIZE_MAX_PX);
        name = "xray.jpg";
        setResizedNote(true);
      }
      const scan = await api.uploadScan(patientId, blob, name);
      router.push(`/scans/${scan.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed. No result was produced.");
      setBusy(false);
    }
  }

  const modelBlocked = meta.model.status === "error" || meta.model.status === "loading";

  return (
    <>
      <PageHeader title="New scan" subtitle="Choose the patient, upload a chest X-ray, then analyze. Results are saved automatically." />
      {!patients && !error && <Loading />}
      {patients && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
          {/* Step 1: patient */}
          <Card className="h-fit p-5">
            <Step n={1} title="Patient" />
            {patients.length > 0 && !adding && (
              <Field label="Screening for">
                <select className={inputCls} value={patientId ?? ""} onChange={(e) => setPatientId(Number(e.target.value))}>
                  {patients.map((p) => <option key={p.id} value={p.id}>{p.name}{p.age != null ? ` (${p.age})` : ""}</option>)}
                </select>
              </Field>
            )}
            {patients.length === 0 && !adding && <p className="text-sm text-muted">No patients yet — add one to continue.</p>}
            {adding ? (
              <div className="mt-2">
                <PatientForm onCancel={patients.length ? () => setAdding(false) : undefined}
                  onSaved={(p) => {
                    setPatients([...patients, { ...p, scan_count: 0, last_scan_at: null }]);
                    setPatientId(p.id);
                    setAdding(false);
                  }} />
              </div>
            ) : (
              <Button variant="ghost" className="mt-3 -ml-2" onClick={() => setAdding(true)}><Icon name="plus" className="h-4 w-4" /> Add a new patient</Button>
            )}
          </Card>

          {/* Step 2: image */}
          <Card className="p-5">
            <Step n={2} title="Chest X-ray" />
            {!preview ? (
              <button type="button" onClick={() => inputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
                onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
                className={cx("flex w-full flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-16 text-center transition",
                  drag ? "border-brand-500 bg-brand-50" : "border-slate-300 hover:border-brand-400 hover:bg-slate-50")}>
                <span className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-600"><Icon name="upload" /></span>
                <span className="font-medium text-ink">Drop an X-ray here, or click to choose</span>
                <span className="text-xs text-muted">JPG or PNG, up to {meta.max_upload_mb} MB</span>
              </button>
            ) : (
              <div className="grid gap-5 md:grid-cols-2">
                <div className="overflow-hidden rounded-xl bg-slate-900">
                  {/* eslint-disable-next-line @next/next/no-img-element -- local preview */}
                  <img src={preview} alt="Selected X-ray preview" className="mx-auto max-h-[420px] w-full object-contain" />
                </div>
                <div className="flex flex-col justify-between gap-4">
                  <div className="space-y-2 text-sm">
                    <div className="font-medium text-ink break-all">{file?.name}</div>
                    <div className="text-muted">{file && (file.size / 1024 / 1024).toFixed(2)} MB</div>
                    <p className="pt-2 text-muted">Check this is the right patient and image. The result is saved automatically at the default threshold ({meta.default_threshold.toFixed(2)}).</p>
                    {resizedNote && <Notice tone="info">Large image resized to {RESIZE_MAX_PX}px for upload. The model analyses a 224×224 version either way.</Notice>}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={analyze} disabled={busy || patientId == null || modelBlocked} className="flex-1">
                      {busy ? <><Spinner /> Analyzing…</> : "Analyze"}
                    </Button>
                    <Button variant="secondary" onClick={() => { setFile(null); setPreview(null); setResizedNote(false); }} disabled={busy}>Change image</Button>
                  </div>
                  {meta.model.status === "loading" && <Notice tone="warn">The model is still loading on the server — this takes about a minute after a cold start.</Notice>}
                  {meta.model.status === "error" && <Notice tone="error">The screening model could not be loaded, so no result can be produced.</Notice>}
                </div>
              </div>
            )}
            <input ref={inputRef} type="file" accept="image/jpeg,image/png" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
            {error && <div className="mt-4"><Notice tone="error">{error}</Notice></div>}
          </Card>
        </div>
      )}
    </>
  );
}

function Step({ n, title }: { n: number; title: string }) {
  return (
    <div className="mb-4 flex items-center gap-2.5">
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-600 text-xs font-bold text-white">{n}</span>
      <h2 className="font-semibold text-ink">{title}</h2>
    </div>
  );
}

async function downscale(file: File, maxPx: number): Promise<Blob> {
  const bmp = await createImageBitmap(file);
  const scale = Math.min(1, maxPx / Math.max(bmp.width, bmp.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bmp.width * scale);
  canvas.height = Math.round(bmp.height * scale);
  canvas.getContext("2d")!.drawImage(bmp, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("Could not resize image."))), "image/jpeg", 0.92));
}
