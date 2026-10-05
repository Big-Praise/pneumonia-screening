import { NextResponse, type NextRequest } from "next/server";

// Forward /api/* to the FastAPI backend (Next.js 16 "proxy", formerly middleware).
// The browser only ever talks to this site, so the httpOnly session cookie stays
// same-origin. Done here rather than with next.config rewrites because:
//  - BACKEND_URL is read at request time, so changing it needs no rebuild;
//  - we can add a request header to EVERY proxied call, including <img> loads.
//    ngrok's free domains show a "You are about to visit…" page to browsers
//    unless this header is present, which would break JSON and image responses.
// TODO (Praise): BACKEND_URL is set in the Vercel project settings.
export function proxy(req: NextRequest) {
  const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
  const target = new URL(req.nextUrl.pathname + req.nextUrl.search, backend);
  const headers = new Headers(req.headers);
  headers.delete("host"); // let the destination's own Host be used (tunnels route by Host)
  headers.set("ngrok-skip-browser-warning", "1");
  return NextResponse.rewrite(target, { request: { headers } });
}

export const config = { matcher: "/api/:path*" };
