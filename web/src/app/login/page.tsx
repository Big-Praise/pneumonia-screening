"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";
import { Disclaimer } from "@/components/disclaimer";
import { Button, Field, Icon, Notice, Spinner, cx, inputCls } from "@/components/ui";
import { api, type Meta } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [tab, setTab] = useState<"login" | "register">("login");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [f, setF] = useState({ username: "", password: "", confirm: "", full_name: "", code: "" });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  useEffect(() => {
    api.me().then(() => router.replace("/dashboard")).catch(() => {}); // already logged in?
    api.meta().then(setMeta).catch(() => setError("Can't reach the server right now. It may be waking up — try again in a minute."));
  }, [router]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (tab === "register" && f.password !== f.confirm) return setError("Passwords do not match.");
    setBusy(true);
    try {
      if (tab === "login") await api.login(f.username, f.password);
      else await api.register({ username: f.username, password: f.password, full_name: f.full_name, registration_code: f.code });
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Disclaimer compact />
      <div className="grid flex-1 lg:grid-cols-2">
        {/* Left: brand panel */}
        <div className="relative hidden overflow-hidden bg-brand-900 p-12 text-white lg:flex lg:flex-col lg:justify-between">
          <div className="absolute -right-32 -top-32 h-96 w-96 rounded-full bg-brand-600/30 blur-3xl" />
          <div className="absolute -bottom-40 -left-20 h-96 w-96 rounded-full bg-teal-400/10 blur-3xl" />
          <div className="relative flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10"><Icon name="lungs" className="h-6 w-6" /></span>
            <span className="text-lg font-semibold">Pneumonia Screening</span>
          </div>
          <div className="relative max-w-md space-y-6">
            <h2 className="text-4xl font-bold leading-tight">Chest X-ray screening, with the reasoning shown.</h2>
            <ul className="space-y-3 text-brand-100">
              {["Screening result with confidence, in seconds",
                "Grad-CAM and LIME explanations side by side",
                "Adjustable threshold, saved patient history, PDF reports"].map((t) => (
                <li key={t} className="flex gap-3"><Icon name="check" className="mt-0.5 h-5 w-5 shrink-0 text-teal-300" />{t}</li>
              ))}
            </ul>
          </div>
          <p className="relative text-sm text-brand-200">Decision-support for qualified clinicians. Not for self-diagnosis.</p>
        </div>

        {/* Right: form */}
        <div className="flex items-center justify-center px-4 py-12 sm:px-8">
          <div className="w-full max-w-sm">
            <h1 className="text-2xl font-bold text-ink">{tab === "login" ? "Welcome back" : "Create a clinician account"}</h1>
            <p className="mt-1 text-sm text-muted">{tab === "login" ? "Log in to continue screening." : "Use a made-up name while testing."}</p>

            <div className="mt-6 grid grid-cols-2 rounded-lg bg-slate-100 p-1 text-sm font-medium">
              {(["login", "register"] as const).map((t) => (
                <button key={t} type="button" onClick={() => { setTab(t); setError(null); }}
                  className={cx("rounded-md py-2 transition", tab === t ? "bg-white text-ink shadow-sm" : "text-slate-500 hover:text-ink")}>
                  {t === "login" ? "Log in" : "Register"}
                </button>
              ))}
            </div>

            <form onSubmit={submit} className="mt-6 space-y-4">
              {tab === "register" && (
                <Field label="Full name (optional)"><input className={inputCls} value={f.full_name} onChange={set("full_name")} autoComplete="name" /></Field>
              )}
              <Field label="Username" hint={tab === "register" ? "3–32 characters: letters, numbers, . _ -" : undefined}>
                <input className={inputCls} value={f.username} onChange={set("username")} autoComplete="username" required />
              </Field>
              <Field label="Password" hint={tab === "register" ? "At least 8 characters." : undefined}>
                <input type="password" className={inputCls} value={f.password} onChange={set("password")}
                  autoComplete={tab === "login" ? "current-password" : "new-password"} required />
              </Field>
              {tab === "register" && (
                <Field label="Confirm password">
                  <input type="password" className={inputCls} value={f.confirm} onChange={set("confirm")} autoComplete="new-password" required />
                </Field>
              )}
              {tab === "register" && meta?.registration_requires_code && (
                <Field label="Registration code" hint="Ask your administrator for the code.">
                  <input type="password" className={inputCls} value={f.code} onChange={set("code")} required />
                </Field>
              )}
              {error && <Notice tone="error">{error}</Notice>}
              <Button type="submit" className="w-full" disabled={busy}>
                {busy && <Spinner />} {tab === "login" ? "Log in" : "Create account"}
              </Button>
              {tab === "register" && meta && !meta.registration_requires_code && (
                <p className="text-center text-xs text-muted">Development mode: registration is open.</p>
              )}
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
