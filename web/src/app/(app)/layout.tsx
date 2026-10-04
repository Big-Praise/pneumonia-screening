"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Disclaimer } from "@/components/disclaimer";
import { SessionContext } from "@/components/session";
import { Icon, Loading, cx } from "@/components/ui";
import { api, type Meta, type User } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: "home" },
  { href: "/scan/new", label: "New scan", icon: "scan" },
  { href: "/patients", label: "Patients", icon: "users" },
];

/** Logged-in shell: auth gate, sidebar, always-on disclaimer, model status. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  // Menu remembers the page it was opened on, so navigating closes it (no effect needed).
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const menuOpen = menuFor === pathname;

  const refreshMeta = useCallback(() => { api.meta().then(setMeta).catch(() => {}); }, []);

  useEffect(() => {
    api.me().then(setUser).catch(() => router.replace("/login"));
    refreshMeta();
  }, [router, refreshMeta]);

  // While the backend is still loading the model (cold start), re-check every 5 s.
  useEffect(() => {
    if (meta?.model.status !== "loading") return;
    const t = setInterval(refreshMeta, 5000);
    return () => clearInterval(t);
  }, [meta?.model.status, refreshMeta]);

  async function logout() {
    await api.logout().catch(() => {});
    router.replace("/login");
  }

  if (!user || !meta) {
    return (<><Disclaimer compact /><Loading label="Opening your workspace…" /></>);
  }

  const model = meta.model;
  const nav = (
    <nav className="flex flex-col gap-1">
      {NAV.map((n) => {
        const active = pathname === n.href || (n.href !== "/dashboard" && pathname.startsWith(n.href)) ||
          (n.href === "/patients" && pathname.startsWith("/scans/"));
        return (
          <Link key={n.href} href={n.href}
            className={cx("flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition",
              active ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100 hover:text-ink")}>
            <Icon name={n.icon} className={active ? "text-brand-600" : "text-slate-400"} />
            {n.label}
          </Link>
        );
      })}
    </nav>
  );

  const sidebarFooter = (
    <div className="space-y-3 border-t border-slate-200 pt-4 text-xs">
      <ModelBadge model={model} />
      <details className="group rounded-lg bg-slate-50 px-3 py-2 text-slate-600">
        <summary className="cursor-pointer font-medium text-slate-700">Known limitations</summary>
        <ul className="mt-2 list-disc space-y-1 pl-4">
          {meta.limitations.map((l) => <li key={l}>{l}</li>)}
        </ul>
      </details>
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-slate-600" title={user.display_name}>
          Signed in as <b className="text-ink">{user.display_name}</b>
        </span>
        <button onClick={logout} className="flex items-center gap-1 rounded-md px-2 py-1 font-medium text-slate-600 hover:bg-slate-100 hover:text-ink">
          <Icon name="logout" className="h-4 w-4" /> Log out
        </button>
      </div>
    </div>
  );

  return (
    <SessionContext.Provider value={{ user, meta, refreshMeta }}>
      <div className="sticky top-0 z-30"><Disclaimer compact /></div>
      {model.status === "demo" && (
        <div className="border-b border-indigo-200 bg-indigo-50 px-4 py-2 text-sm text-indigo-950">
          🧪 <b>DEMO MODE</b> — no trained model is loaded. Results are placeholders and mean nothing clinically.
        </div>
      )}
      {model.status === "error" && (
        <div className="border-b border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-900">
          The screening model could not be loaded, so new scans can&apos;t be analysed. Saved results are still viewable.
        </div>
      )}

      {/* Mobile top bar */}
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 lg:hidden">
        <Brand />
        <button onClick={() => setMenuFor(menuOpen ? null : pathname)} aria-label="Menu" className="rounded-md p-2 hover:bg-slate-100">
          <Icon name="menu" />
        </button>
      </header>
      {menuOpen && <div className="space-y-4 border-b border-slate-200 bg-white p-4 lg:hidden">{nav}{sidebarFooter}</div>}

      <div className="mx-auto flex max-w-[1400px]">
        <aside className="sticky top-10 hidden h-[calc(100vh-2.5rem)] w-64 shrink-0 flex-col justify-between border-r border-slate-200 bg-white p-5 lg:flex">
          <div className="space-y-6"><Brand />{nav}</div>
          {sidebarFooter}
        </aside>
        <main className="min-w-0 flex-1 px-4 py-6 sm:px-8 sm:py-8">{children}</main>
      </div>
    </SessionContext.Provider>
  );
}

function Brand() {
  return (
    <Link href="/dashboard" className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600 text-white">
        <Icon name="lungs" className="h-5 w-5" />
      </span>
      <span className="leading-tight">
        <span className="block text-[15px] font-bold text-ink">Pneumonia Screening</span>
        <span className="block text-[11px] text-muted">Clinical decision-support</span>
      </span>
    </Link>
  );
}

function ModelBadge({ model }: { model: Meta["model"] }) {
  const map = {
    ready: ["bg-emerald-500", `Model: ${model.source}`],
    demo: ["bg-indigo-500", "Model: DEMO (mock)"],
    loading: ["bg-amber-400 animate-pulse", "Model: loading…"],
    error: ["bg-rose-500", "Model: failed to load"],
  } as const;
  const [dot, text] = map[model.status];
  return (
    <div className="flex items-center gap-2 text-slate-600">
      <span className={cx("h-2 w-2 rounded-full", dot)} /> {text}
    </div>
  );
}
