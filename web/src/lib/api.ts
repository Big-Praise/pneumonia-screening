// Thin client for the FastAPI backend. Same-origin (/api is proxied), so the
// httpOnly session cookie is sent automatically and never touched by JS.

export type Label = "NORMAL" | "PNEUMONIA";

export interface User { id: number; username: string; full_name: string | null; display_name: string }
export interface ModelStatus { status: "loading" | "ready" | "demo" | "error"; source: string | null; error: string | null }
export interface Meta {
  disclaimer: string;
  limitations: string[];
  registration_requires_code: boolean;
  model: ModelStatus;
  default_threshold: number;
  default_opacity: number;
  lime_num_samples: number;
  max_upload_mb: number;
}
export interface Patient {
  id: number; name: string; age: number | null; sex: string | null; note: string | null; created_at: string;
}
export interface PatientSummary extends Patient { scan_count: number; last_scan_at: string | null }
export interface Scan {
  id: number; patient_id: number; created_at: string; predicted_label: Label;
  confidence: number; pneumonia_prob: number; threshold_used: number;
}
export interface LimeLabelInfo { has_regions: boolean; weak: boolean; agreement: number | null }
export interface LimeStatus {
  status: "none" | "queued" | "running" | "done" | "error";
  progress: number;
  labels?: Record<Label, LimeLabelInfo>;
}
export interface ScanDetail extends Scan { patient: Patient; lime: LimeStatus; model: ModelStatus }
export interface Dashboard { patients: number; scans: number; recent: (Scan & { patient_name: string })[] }

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { ...init, credentials: "same-origin", cache: "no-store" });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }
  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/api/auth/")) {
    // Full reload on purpose: session expired, so drop all in-memory state.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/login";
  }
  if (!res.ok) {
    // A non-JSON error means the request never reached our API: the tunnel or the
    // backend PC is offline (ngrok/Cloudflare answer with their own HTML pages).
    if (!(res.headers.get("content-type") ?? "").includes("application/json")) {
      throw new ApiError(res.status,
        "The screening server is offline right now. It runs on the host PC — please try again once it's started.");
    }
    let msg = res.status >= 500
      ? "The server had a problem. No result was changed — please try again."
      : `Request failed (${res.status}).`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") msg = body.detail;
      else if (Array.isArray(body.detail)) msg = "Please check the form values.";
    } catch { /* non-JSON error body */ }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

export const api = {
  meta: () => request<Meta>("/api/meta"),
  me: () => request<User>("/api/auth/me"),
  login: (username: string, password: string) => request<User>("/api/auth/login", json("POST", { username, password })),
  register: (b: { username: string; password: string; full_name: string; registration_code: string }) =>
    request<User>("/api/auth/register", json("POST", b)),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  dashboard: () => request<Dashboard>("/api/dashboard"),
  patients: () => request<PatientSummary[]>("/api/patients"),
  createPatient: (b: { name: string; age: number | null; sex: string | null; note: string | null }) =>
    request<Patient>("/api/patients", json("POST", b)),
  patient: (id: number) => request<Patient & { scans: Scan[] }>(`/api/patients/${id}`),
  updatePatient: (id: number, b: { name: string; age: number | null; sex: string | null; note: string | null }) =>
    request<Patient>(`/api/patients/${id}`, json("PATCH", b)),
  deletePatient: (id: number) => request<{ deleted_scans: number }>(`/api/patients/${id}`, { method: "DELETE" }),
  deleteScan: (id: number) => request<{ ok: boolean }>(`/api/scans/${id}`, { method: "DELETE" }),
  uploadScan: (patientId: number, file: Blob, filename: string) => {
    const fd = new FormData();
    fd.append("file", file, filename);
    return request<Scan>(`/api/patients/${patientId}/scans`, { method: "POST", body: fd });
  },
  scan: (id: number) => request<ScanDetail>(`/api/scans/${id}`),
  saveThreshold: (id: number, threshold: number) => request<Scan>(`/api/scans/${id}`, json("PATCH", { threshold })),
  // wait > 0: long-poll (server holds up to `wait` s) — keeps the backend CPU awake on Cloud Run.
  limeStatus: (id: number, wait = 0) => request<LimeStatus>(`/api/scans/${id}/lime${wait ? `?wait=${wait}` : ""}`),
  limeStart: (id: number) => request<LimeStatus>(`/api/scans/${id}/lime`, { method: "POST" }),
};

export const urls = {
  image: (id: number, thumb = false) => `/api/scans/${id}/image${thumb ? "?thumb=1" : ""}`,
  gradcam: (id: number, label: Label) => `/api/scans/${id}/gradcam?label=${label}`,
  lime: (id: number, label: Label) => `/api/scans/${id}/lime/image?label=${label}`,
  report: (id: number) => `/api/scans/${id}/report.pdf?tz_offset_min=${-new Date().getTimezoneOffset()}`,
};

/** Same rule as the backend (predict.classify): PNEUMONIA when p >= threshold. */
export function classify(p: number, threshold: number): { label: Label; confidence: number } {
  return p >= threshold ? { label: "PNEUMONIA", confidence: p } : { label: "NORMAL", confidence: 1 - p };
}

export function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}
