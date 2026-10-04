import type { NextConfig } from "next";

// The browser only ever talks to this Next.js app. /api/* is proxied to the
// FastAPI backend, so the session cookie is same-origin (httpOnly, SameSite=Lax)
// and no CORS is needed. TODO (Praise): set BACKEND_URL in Vercel to the
// Hugging Face Space URL, e.g. https://big-praise-pneumonia-api.hf.space
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
