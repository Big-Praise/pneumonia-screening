"""Run the API on this PC and expose it to the Vercel site through a tunnel ($0).
Patient data and X-rays stay on this machine (app.db + uploads/).

    .venv\\Scripts\\python serve_public.py              # backend + tunnel
    .venv\\Scripts\\python serve_public.py --deploy     # ...and redeploy Vercel with the URL
    .venv\\Scripts\\python serve_public.py --cloudflare # force the Cloudflare fallback

Tunnels:
- ngrok (used when NGROK_DOMAIN is set in .env.backend): a permanent free
  domain, so the Vercel site never needs redeploying. Needs tools/ngrok.exe and
  `tools\\ngrok.exe config add-authtoken ...` done once.
- Cloudflare quick tunnel (fallback): no account, but a new random URL on each
  start, so use --deploy to point Vercel at it (~1 minute).
Keep this window open while the site is in use; Ctrl+C stops everything.

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
TOOLS = ROOT / "tools"
EXE = ".exe" if os.name == "nt" else ""
CLOUDFLARED = TOOLS / f"cloudflared{EXE}"
NGROK = TOOLS / f"ngrok{EXE}"
URL_FILE = TOOLS / "tunnel_url.txt"
PORT = 8000
TUNNEL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def load_env() -> dict:
    if not ENV_FILE.exists():
        ENV_FILE.write_text(
            "# Local backend settings for serve_public.py. Keep private; never commit.\n"
            f"JWT_SECRET={secrets.token_urlsafe(48)}\n"
            "# Share this code only with people who should be able to create accounts.\n"
            f"REGISTRATION_CODE={secrets.token_urlsafe(9)}\n"
            "# Optional: your free ngrok static domain (permanent URL), e.g. name.ngrok-free.dev\n"
            "NGROK_DOMAIN=\n",
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
            req = urllib.request.Request(url, headers={"ngrok-skip-browser-warning": "1"})
            with urllib.request.urlopen(req, timeout=10) as r:
                if want in r.read().decode():
                    return True
        except Exception:  # noqa: BLE001 — not up yet
            pass
        time.sleep(2)
    return False


def start_ngrok(domain: str) -> tuple[subprocess.Popen, str]:
    url = "https://" + domain.removeprefix("https://").strip("/")
    print(f"Opening ngrok tunnel on {url} …")
    proc = subprocess.Popen([str(NGROK), "http", str(PORT), "--url", url, "--log", "stdout"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc, url


def start_cloudflare() -> tuple[subprocess.Popen, str | None]:
    print("Opening Cloudflare tunnel …")
    proc = subprocess.Popen(
        [str(CLOUDFLARED), "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{PORT}"],
        stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, encoding="utf-8",
        errors="replace")
    url = None
    for line in proc.stderr:  # cloudflared logs the public URL on stderr
        m = TUNNEL_RE.search(line)
        if m:
            url = m.group(0)
            break
    # Keep draining cloudflared's log so its pipe never fills up and blocks it.
    threading.Thread(target=lambda: [None for _ in proc.stderr], daemon=True).start()
    return proc, url


def deploy_vercel(url: str) -> None:
    vercel = shutil.which("vercel") or shutil.which("vercel.cmd")
    if not vercel:
        print("Vercel CLI not found; skipping deploy.")
        return
    print("Redeploying the Vercel site with this backend URL (~1 min) …")
    out = subprocess.run([vercel, "deploy", "--prod", "--yes", "--env", f"BACKEND_URL={url}"],
                         cwd=ROOT / "web", capture_output=True, text=True)
    site = re.findall(r"https://[^\s\"]+\.vercel\.app", out.stdout + out.stderr)
    if out.returncode == 0:
        print("Vercel deployed:", site[-1] if site else "(see Vercel dashboard)")
    else:
        print("Vercel deploy failed:\n", (out.stderr or out.stdout)[-1500:])


def main() -> int:
    deploy = "--deploy" in sys.argv
    settings = load_env()
    domain = settings.get("NGROK_DOMAIN", "")
    use_ngrok = bool(domain) and "--cloudflare" not in sys.argv
    tool = NGROK if use_ngrok else CLOUDFLARED
    if not tool.exists():
        print(f"Missing {tool}. See README (Tunnel mode) to download it.")
        return 1

    env = {**os.environ, **settings, "COOKIE_SECURE": "1", "TF_CPP_MIN_LOG_LEVEL": "2"}
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

        tunnel, url = start_ngrok(domain) if use_ngrok else start_cloudflare()
        procs.append(tunnel)
        if not url:
            print("Could not get a tunnel URL.")
            return 1
        print(f"Tunnel URL: {url}  (waiting for it to become reachable …)")
        if not wait_for(f"{url}/api/health", 120):
            print("Tunnel did not become reachable. Try restarting."
                  + (" (ngrok: authtoken added? domain correct? another ngrok already running?)"
                     if use_ngrok else ""))
            return 1
        URL_FILE.write_text(url, encoding="utf-8")
        print(f"Backend is public at {url}")

        if deploy:
            deploy_vercel(url)
        elif use_ngrok:
            print("Permanent ngrok URL: the Vercel site needs no redeploy.")

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
