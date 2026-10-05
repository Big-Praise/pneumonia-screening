"""API tests: auth/cookies, per-user scoping, full scan flow, LIME job, PDF.
Run against the mock predictor (no model file needed) and both blob backends."""
import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import config
from api import security, services
from api.main import app


def _xray_bytes(seed=1) -> bytes:
    import numpy as np
    arr = np.random.default_rng(seed).integers(0, 255, (300, 300), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(params=["disk", "db"])
def client(request, monkeypatch):
    monkeypatch.setattr(config, "BLOB_BACKEND", request.param)
    monkeypatch.setattr(config, "COOKIE_SECURE", False)      # TestClient speaks http
    monkeypatch.setattr(config, "MODEL_CANDIDATES", [])       # force the mock predictor
    monkeypatch.setattr(config, "MODEL_HF_REPO", "")
    monkeypatch.setattr(config, "LIME_NUM_SAMPLES", 20)
    monkeypatch.setattr(security, "throttle", security.LoginThrottle())
    services.display_image.cache_clear()
    services.heatmap.cache_clear()
    with TestClient(app) as c:
        for _ in range(100):                                  # model loads in a thread
            if services.model.status()["status"] != "loading":
                break
            time.sleep(0.05)
        yield c


def _register(c, username="dr.a", password="password-a"):
    r = c.post("/api/auth/register", json={"username": username, "password": password,
                                           "full_name": "Dr Test"})
    assert r.status_code == 200, r.text
    return r


def test_meta_is_public_and_shows_demo(client):
    r = client.get("/api/meta").json()
    assert r["model"]["status"] == "demo"
    assert "not a diagnosis" in r["disclaimer"]


def test_auth_cookie_flow(client):
    assert client.get("/api/auth/me").status_code == 401
    r = _register(client)
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert client.get("/api/auth/me").json()["username"] == "dr.a"
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    bad = client.post("/api/auth/login", json={"username": "dr.a", "password": "nope-nope"})
    assert bad.status_code == 401 and bad.json()["detail"] == "Incorrect username or password."
    assert client.post("/api/auth/login", json={"username": "dr.a", "password": "password-a"}).is_success


def test_forged_or_garbage_token_rejected(client):
    client.cookies.set(security.COOKIE, "not-a-jwt")
    assert client.get("/api/auth/me").status_code == 401


def test_login_throttle(client):
    _register(client)
    client.post("/api/auth/logout")
    for _ in range(security.LoginThrottle.MAX_FAILS):
        client.post("/api/auth/login", json={"username": "dr.a", "password": "wrong-pass"})
    r = client.post("/api/auth/login", json={"username": "dr.a", "password": "password-a"})
    assert r.status_code == 429


def test_full_scan_flow(client):
    _register(client)
    pid = client.post("/api/patients", json={"name": "Test Patient", "age": 30}).json()["id"]

    r = client.post(f"/api/patients/{pid}/scans",
                    files={"file": ("x.png", _xray_bytes(), "image/png")})
    assert r.status_code == 201, r.text
    scan = r.json()
    assert scan["predicted_label"] in ("NORMAL", "PNEUMONIA") and scan["threshold_used"] == 0.5

    sid = scan["id"]
    detail = client.get(f"/api/scans/{sid}").json()
    assert detail["patient"]["name"] == "Test Patient" and detail["lime"]["status"] == "none"

    img = client.get(f"/api/scans/{sid}/image")
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/scans/{sid}/image?thumb=1").status_code == 200
    for label in ("NORMAL", "PNEUMONIA"):
        assert client.get(f"/api/scans/{sid}/gradcam?label={label}").status_code == 200
    assert client.get(f"/api/scans/{sid}/gradcam?label=BAD").status_code == 400

    saved = client.patch(f"/api/scans/{sid}", json={"threshold": 0.99}).json()
    assert saved["threshold_used"] == 0.99
    assert client.patch(f"/api/scans/{sid}", json={"threshold": 2}).status_code == 422

    # LIME: start -> poll -> done -> images + summary
    assert client.get(f"/api/scans/{sid}/lime/image?label=NORMAL").status_code == 404
    assert client.post(f"/api/scans/{sid}/lime").status_code == 202
    for _ in range(300):
        st = client.get(f"/api/scans/{sid}/lime").json()
        if st["status"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert st["status"] == "done", st
    assert set(st["labels"]) == {"NORMAL", "PNEUMONIA"}
    assert client.get(f"/api/scans/{sid}/lime/image?label=PNEUMONIA").status_code == 200

    pdf = client.get(f"/api/scans/{sid}/report.pdf?tz_offset_min=60")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert "Test Patient" not in pdf.headers["content-disposition"]

    dash = client.get("/api/dashboard").json()
    assert dash["patients"] == 1 and dash["scans"] == 1
    hist = client.get(f"/api/patients/{pid}").json()
    assert [s["id"] for s in hist["scans"]] == [sid]


def test_bad_upload_rejected(client):
    _register(client)
    pid = client.post("/api/patients", json={"name": "Test Patient"}).json()["id"]
    r = client.post(f"/api/patients/{pid}/scans", files={"file": ("x.png", b"junk", "image/png")})
    assert r.status_code == 400 and "readable" in r.json()["detail"]


def test_records_scoped_to_owner(client):
    _register(client, "dr.a", "password-a")
    pid = client.post("/api/patients", json={"name": "A's Patient"}).json()["id"]
    sid = client.post(f"/api/patients/{pid}/scans",
                      files={"file": ("x.png", _xray_bytes(), "image/png")}).json()["id"]
    client.post("/api/auth/logout")
    _register(client, "dr.b", "password-b")
    assert client.get("/api/patients").json() == []
    for url in (f"/api/patients/{pid}", f"/api/scans/{sid}", f"/api/scans/{sid}/image",
                f"/api/scans/{sid}/report.pdf"):
        assert client.get(url).status_code == 404, url
    assert client.patch(f"/api/scans/{sid}", json={"threshold": 0.1}).status_code == 404
    assert client.post(f"/api/patients/{pid}/scans",
                       files={"file": ("x.png", _xray_bytes(), "image/png")}).status_code == 404


def test_data_endpoints_require_login(client):
    for method, url in [("get", "/api/dashboard"), ("get", "/api/patients"),
                        ("post", "/api/patients"), ("get", "/api/scans/1")]:
        assert getattr(client, method)(url).status_code == 401, url


def test_blocking_model_load_ready_at_startup(monkeypatch):
    """Cloud Run mode: the model is loaded before the first request is served."""
    monkeypatch.setattr(config, "MODEL_LOAD_BLOCKING", True)
    monkeypatch.setattr(config, "MODEL_CANDIDATES", [])
    monkeypatch.setattr(config, "MODEL_HF_REPO", "")
    monkeypatch.setattr(services, "model", services.ModelState())
    import api.main as main
    monkeypatch.setattr(main, "model", services.model)
    with TestClient(app) as c:
        assert c.get("/api/health").json()["model"] == "demo"   # no waiting needed


def test_lime_long_poll_returns_when_done(client):
    _register(client)
    pid = client.post("/api/patients", json={"name": "Test Patient"}).json()["id"]
    sid = client.post(f"/api/patients/{pid}/scans",
                      files={"file": ("x.png", _xray_bytes(), "image/png")}).json()["id"]
    client.post(f"/api/scans/{sid}/lime")
    st = client.get(f"/api/scans/{sid}/lime?wait=25").json()   # held open until finished
    for _ in range(5):
        if st["status"] == "done":
            break
        st = client.get(f"/api/scans/{sid}/lime?wait=25").json()
    assert st["status"] == "done" and "labels" in st


def test_edit_and_delete_endpoints(client):
    import blobstore
    import lime_explain
    _register(client)
    pid = client.post("/api/patients", json={"name": "Test Patient", "age": 30}).json()["id"]
    sids = [client.post(f"/api/patients/{pid}/scans",
                        files={"file": ("x.png", _xray_bytes(i), "image/png")}).json()["id"]
            for i in (1, 2)]

    r = client.patch(f"/api/patients/{pid}", json={"name": "Renamed Patient", "age": 31, "sex": "Male"})
    assert r.status_code == 200 and r.json()["name"] == "Renamed Patient"
    assert client.patch(f"/api/patients/{pid}", json={"name": "  "}).status_code == 400

    # LIME result for scan 0, then delete scan 0: image + LIME blobs both gone.
    client.post(f"/api/scans/{sids[0]}/lime")
    client.get(f"/api/scans/{sids[0]}/lime?wait=25")
    img = client.get(f"/api/scans/{sids[0]}").json()
    import db as _db
    path0 = _db.get_scan(1, sids[0])[0].image_path
    assert blobstore.exists(path0) and blobstore.exists(lime_explain.cache_name(path0))
    assert client.delete(f"/api/scans/{sids[0]}").json() == {"ok": True}
    assert client.get(f"/api/scans/{sids[0]}").status_code == 404
    assert not blobstore.exists(path0) and not blobstore.exists(lime_explain.cache_name(path0))
    assert img["patient"]["name"] == "Renamed Patient"

    # Other clinicians can't edit or delete.
    path1 = _db.get_scan(1, sids[1])[0].image_path
    client.post("/api/auth/logout")
    _register(client, "dr.b", "password-b")
    assert client.patch(f"/api/patients/{pid}", json={"name": "Hijack"}).status_code == 404
    assert client.delete(f"/api/patients/{pid}").status_code == 404
    assert client.delete(f"/api/scans/{sids[1]}").status_code == 404
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "dr.a", "password": "password-a"})

    # Delete patient: cascades to the remaining scan and its stored image.
    assert client.delete(f"/api/patients/{pid}").json() == {"deleted_scans": 1}
    assert client.get(f"/api/patients/{pid}").status_code == 404
    assert client.get(f"/api/scans/{sids[1]}").status_code == 404
    assert not blobstore.exists(path1)
    assert client.get("/api/dashboard").json()["scans"] == 0


def test_change_password_logs_out_other_sessions(client):
    _register(client)                                   # device 1
    other = TestClient(app)                             # device 2, same account
    assert other.post("/api/auth/login", json={"username": "dr.a", "password": "password-a"}).status_code == 200
    assert other.get("/api/auth/me").status_code == 200

    bad = client.post("/api/auth/password", json={"current_password": "nope-nope", "new_password": "brand-new-pass"})
    assert bad.status_code == 400 and "incorrect" in bad.json()["detail"]
    ok = client.post("/api/auth/password", json={"current_password": "password-a", "new_password": "brand-new-pass"})
    assert ok.status_code == 200

    assert client.get("/api/auth/me").status_code == 200      # this device: fresh cookie
    assert other.get("/api/auth/me").status_code == 401       # other device: logged out
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"username": "dr.a", "password": "password-a"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "dr.a", "password": "brand-new-pass"}).status_code == 200
    assert client.post("/api/auth/password", json={"current_password": "x", "new_password": "y"}).status_code in (400, 401)
