"""Run the API on this PC and expose it to the Vercel site through a Cloudflare
quick tunnel ($0, no account). Patient data and X-rays stay on this machine
(app.db + uploads/).

    .venv\\Scripts\\python serve_public.py            # backend + tunnel
    .venv\\Scripts\\python serve_public.py --deploy   # ...and redeploy Vercel with the new URL

Quick-tunnel URLs change on every start, which is why --deploy exists: it
rebuilds the Vercel site pointing at the new URL (~1 minute). Keep this window
open while the site is in use; Ctrl+C stops everything.

First run creates .env.backend (git-ignored) with a random JWT_SECRET and
REGISTRATION_CODE. Secrets are never printed — open the file to read the code.
"""
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env.backend"
CLOUDFLARED = ROOT / "tools" / ("cloudflared.exe" if os.name == "nt" else "cloudflared")
URL_FILE = ROOT / "tools" / "tunnel_url.txt"
PORT = 8000
TUNNEL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def load_env() -> dict:
    if not ENV_FILE.exists():
        ENV_FILE.write_text(
            "# Local backend settings for serve_public.py. Keep private; never commit.\n"
            f"JWT_SECRET={secrets.token_urlsafe(48)}\n"
            "# Share this code only with people who should be able to create accounts.\n"
            f"REGISTRATION_CODE={secrets.token_urlsafe(9)}\n",
            encoding="utf-8",
        )
        print(f"Created {ENV_FILE.name} with a new session key and registration code "
              "(open the file to see the code).")
    env = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def wait_for(url: str, timeout: float, want: str = '"ok":true') -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                if want in r.read().decode():
                    return True
        except Exception:  # noqa: BLE001 — not up yet
            pass
        time.sleep(2)
    return False


def main() -> int:
    deploy = "--deploy" in sys.argv
    if not CLOUDFLARED.exists():
        print(f"Missing {CLOUDFLARED}. See README (Tunnel mode) to download cloudflared.")
        return 1

    env = {**os.environ, **load_env(), "COOKIE_SECURE": "1", "TF_CPP_MIN_LOG_LEVEL": "2"}
    procs: list[subprocess.Popen] = []
    try:
        print(f"Starting backend on http://127.0.0.1:{PORT} …")
        procs.append(subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1",
             "--port", str(PORT), "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"],
            cwd=ROOT, env=env))
        if not wait_for(f"http://127.0.0.1:{PORT}/api/health", 180, want='"model":"ready"'):
            print("Backend did not become ready (model not loaded?). Check the log above.")
            return 1
        print("Backend ready (real model loaded).")

        print("Opening Cloudflare tunnel …")
        tunnel = subprocess.Popen(
            [str(CLOUDFLARED), "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{PORT}"],
            stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace")
        procs.append(tunnel)
        url = None
        for line in tunnel.stderr:  # cloudflared logs the public URL on stderr
            m = TUNNEL_RE.search(line)
            if m:
                url = m.group(0)
                break
        if not url:
            print("Could not get a tunnel URL from cloudflared.")
            return 1
        # Keep draining cloudflared's log so its pipe never fills up and blocks it.
        threading.Thread(target=lambda: [None for _ in tunnel.stderr], daemon=True).start()

        print(f"Tunnel URL: {url}  (waiting for it to become reachable …)")
        if not wait_for(f"{url}/api/health", 120):
            print("Tunnel did not become reachable. Try restarting.")
            return 1
        URL_FILE.write_text(url, encoding="utf-8")
        print(f"Backend is public at {url}")

        if deploy:
            vercel = shutil.which("vercel") or shutil.which("vercel.cmd")
            if not vercel:
                print("Vercel CLI not found; skipping deploy.")
            else:
                print("Redeploying the Vercel site with the new backend URL (~1 min) …")
                out = subprocess.run(
                    [vercel, "deploy", "--prod", "--yes",
                     "--build-env", f"BACKEND_URL={url}", "--env", f"BACKEND_URL={url}"],
                    cwd=ROOT / "web", capture_output=True, text=True)
                site = re.findall(r"https://[^\s]+\.vercel\.app", out.stdout + out.stderr)
                if out.returncode == 0:
                    print("Vercel deployed:", site[-1] if site else "(see Vercel dashboard)")
                else:
                    print("Vercel deploy failed:\n", (out.stderr or out.stdout)[-1500:])

        print("\nRunning. Keep this window open while the site is in use. Ctrl+C to stop.")
        while all(p.poll() is None for p in procs):
            time.sleep(1)
        print("A process exited; shutting down.")
        return 1
    except KeyboardInterrupt:
        print("\nStopping …")
        return 0
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()


if __name__ == "__main__":
    sys.exit(main())
