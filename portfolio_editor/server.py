from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
import json
import os
import re
import secrets
import subprocess
import threading
import time
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "illustration" / "content.json"
UPLOADS = ROOT / "media" / "illustration" / "uploads"
HOST = "127.0.0.1"
PORT = 8765
MAX_UPLOAD = 40 * 1024 * 1024
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

DEFAULT_MANIFEST = {
    "showLegacyProcessAtlas": True,
    "showLegacyGalleryAtlas": True,
    "process": [
        {"slot": "Line Art", "src": "", "title": "Line Art"},
        {"slot": "Color Pass", "src": "", "title": "Color Pass"},
        {"slot": "Final Lighting", "src": "", "title": "Final Lighting"},
    ],
    "gallery": [],
}


def ensure_layout():
    (ROOT / "illustration").mkdir(parents=True, exist_ok=True)
    UPLOADS.mkdir(parents=True, exist_ok=True)
    if not MANIFEST.exists():
        MANIFEST.write_text(json.dumps(DEFAULT_MANIFEST, indent=2) + "\n", encoding="utf-8")


def safe_name(name: str) -> str:
    name = Path(name).name
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValueError("Unsupported image type. Use PNG, JPG, WEBP or GIF.")
    stem = Path(name).stem
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-").lower() or "image"
    return stem + ext


def safe_upload_path(src: str) -> Path:
    rel = unquote(src).lstrip("/")
    target = (ROOT / rel).resolve()
    uploads = UPLOADS.resolve()
    if uploads not in target.parents:
        raise ValueError("Only editor-managed uploads can be deleted.")
    return target


def run_git(args):
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace"
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        print("[editor]", fmt % args)

    def json_response(self, data, status=200):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 2 * 1024 * 1024:
            raise ValueError("Invalid request size.")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path).path
        if path in {"/", "/editor", "/editor/"}:
            self.path = "/portfolio_editor/index.html"
            return super().do_GET()
        if path == "/api/content":
            try:
                data = json.loads(MANIFEST.read_text(encoding="utf-8"))
                return self.json_response(data)
            except Exception as e:
                return self.json_response({"error": str(e)}, 500)
        if path == "/api/status":
            branch_code, branch = run_git(["branch", "--show-current"])
            return self.json_response({
                "root": str(ROOT),
                "branch": branch.strip() if branch_code == 0 else "",
                "localhost": f"http://{HOST}:{PORT}/",
            })
        if "/.git/" in path or path.startswith("/.git"):
            self.send_error(404)
            return
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/content":
                data = self.read_json()
                if not isinstance(data, dict):
                    raise ValueError("Invalid portfolio data.")
                if not isinstance(data.get("process", []), list) or not isinstance(data.get("gallery", []), list):
                    raise ValueError("Invalid portfolio structure.")
                tmp = MANIFEST.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                os.replace(tmp, MANIFEST)
                return self.json_response({"ok": True})

            if path == "/api/upload":
                qs = parse_qs(urlparse(self.path).query)
                original = qs.get("name", [""])[0]
                prefix = re.sub(r"[^a-z]+", "", qs.get("prefix", ["gallery"])[0].lower()) or "gallery"
                filename = safe_name(original)
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_UPLOAD:
                    raise ValueError("Image is empty or larger than 40 MB.")
                raw = self.rfile.read(length)
                final = f"{int(time.time()*1000)}-{secrets.token_hex(2)}-{prefix}-{filename}"
                dest = UPLOADS / final
                dest.write_bytes(raw)
                return self.json_response({"ok": True, "src": "/media/illustration/uploads/" + final})

            if path == "/api/publish":
                log = []
                code, out = run_git(["add", "-A", "illustration/content.json", "media/illustration/uploads"])
                log.append(out)
                if code != 0:
                    return self.json_response({"ok": False, "log": "".join(log)}, 500)

                diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
                if diff.returncode == 1:
                    code, out = run_git(["commit", "-m", "Update illustration portfolio"])
                    log.append(out)
                    if code != 0:
                        return self.json_response({"ok": False, "log": "".join(log)}, 500)

                code, out = run_git(["pull", "--rebase", "origin", "main"])
                log.append(out)
                if code != 0:
                    return self.json_response({"ok": False, "log": "".join(log)}, 500)

                code, out = run_git(["push", "origin", "main"])
                log.append(out)
                return self.json_response({"ok": code == 0, "log": "".join(log)}, 200 if code == 0 else 500)

            self.send_error(404)
        except Exception as e:
            self.json_response({"ok": False, "error": str(e)}, 400)

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path != "/api/file":
            self.send_error(404)
            return
        try:
            qs = parse_qs(urlparse(self.path).query)
            src = qs.get("src", [""])[0]
            target = safe_upload_path(src)
            if target.exists():
                target.unlink()
            self.json_response({"ok": True})
        except Exception as e:
            self.json_response({"ok": False, "error": str(e)}, 400)


def open_browser():
    time.sleep(0.7)
    webbrowser.open(f"http://{HOST}:{PORT}/")


if __name__ == "__main__":
    ensure_layout()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Portfolio editor running at http://{HOST}:{PORT}/")
    print(f"Repository: {ROOT}")
    threading.Thread(target=open_browser, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
