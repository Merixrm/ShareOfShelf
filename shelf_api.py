"""Read-only detection API for the web app — upload a shelf photo, get SKUs back.

    python shelf_api.py            # then point web-base44 at http://127.0.0.1:8001

It runs the same detect -> embed -> match -> gate steps as `main.py` and adds the
share-of-shelf aggregation `main.py` computes after a full run, so a single
request gives the frontend everything it needs to render facings and percentages
for one photo. It never writes to the knowledge base.

Dependency-free (stdlib http.server, no build step) plus CORS headers, since the
browser calls this on its own origin/port rather than through Vite's dev-server
proxy (which owns "/api" for the Base44 backend and would otherwise swallow a
same-origin request).
"""

import argparse
import json
import mimetypes
import re
import threading
import traceback
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from src.classifier import is_non_beverage

ROOT       = Path(__file__).resolve().parent
DATA_DIR   = ROOT / "data"
KB_PATH    = DATA_DIR / "knowledge_base" / "crops" / "object"
MODEL_PATH = ROOT / "models" / "best.pt"
SESSION_DIR = DATA_DIR / "_api_sessions"  # per-session crops (gitignored)
UPLOAD_DIR  = DATA_DIR / "_uploads"       # uploaded shelf photos (gitignored)


# ── Engine: models + knowledge base (read-only) ─────────────────────────────

class Engine:
    """Loaded models + a read-only KB view. Torch/index access is serialised by
    `lock`, taken per crop so one slow embed doesn't block the others queuing up
    behind it any longer than necessary."""

    def __init__(self, args):
        self.args   = args
        self.lock   = threading.RLock()
        self.status = "loading"      # loading | ready | error
        self.error  = None
        self.yolo = self.img2vec = self.index = None

    def warmup(self):
        try:
            from ultralytics import YOLO

            from src.classifier import KBIndex, load_kb_embeddings
            from src.img2vec_dino2 import Img2VecDino2
            from src.img2vec_resnet18 import Img2VecResnet18

            print(f"Loading detector {MODEL_PATH}…")
            self.yolo = YOLO(str(MODEL_PATH))
            print(f"Loading embedding model ({self.args.model})…")
            self.img2vec = (Img2VecDino2() if self.args.model == "dino2"
                            else Img2VecResnet18())
            print("Loading knowledge base…")
            classes, embeddings = load_kb_embeddings(str(KB_PATH), self.img2vec)
            self.index = KBIndex(classes, embeddings)
            print(f"Ready — {len(self.index.products)} products, "
                  f"{len(embeddings)} reference images.")
            self.status = "ready"
        except Exception as e:
            self.status = "error"
            self.error  = f"{e.__class__.__name__}: {e}"
            traceback.print_exc()


ENGINE   = None
SESSIONS = {}
SESS_LOCK = threading.Lock()


# ── Detection session ───────────────────────────────────────────────────────

def start_session(image_path, use_tta):
    sid = uuid.uuid4().hex[:8]
    session = {
        "id": sid,
        "status": "running",         # running | ready | error
        "stage": "detecting",
        "done": 0, "total": 0,
        "width": 0, "height": 0,
        "crops": [],
        "share_of_shelf": [],
        "total_facings": 0,
        "error": None,
    }
    with SESS_LOCK:
        SESSIONS[sid] = session
    threading.Thread(target=_run_session, args=(session, image_path, use_tta), daemon=True).start()
    return session


def _run_session(session, image_path, use_tta):
    from PIL import Image

    from src.classifier import apply_gates, classify_full
    from src.detect import detect_products, save_crops
    from src.img2vec_dino2 import Img2VecDino2

    args = ENGINE.args
    try:
        img = Image.open(image_path)
        session["width"], session["height"] = img.size
        img.close()

        with ENGINE.lock:
            boxes, _confs = detect_products(ENGINE.yolo, image_path)
            crops = save_crops(image_path, boxes, SESSION_DIR / session["id"], session["id"])

        session["total"] = len(crops)
        session["stage"] = "classifying"
        tta = use_tta and isinstance(ENGINE.img2vec, Img2VecDino2)

        facings = Counter()
        area_by_product = defaultdict(float)
        total_area = 0.0

        for i, crop in enumerate(crops):
            with ENGINE.lock:
                im = Image.open(crop["path"])
                vec = (ENGINE.img2vec.getRobustVec(im) if tta
                       else ENGINE.img2vec.getVec(im))
                im.close()

                label, vote_conf, score, margin = classify_full(vec, ENGINE.index,
                                                                mode=args.match_mode)
                gated = apply_gates(label, vote_conf, score, args.conf_threshold,
                                    args.sim_threshold, margin=margin,
                                    margin_threshold=args.margin_threshold)

            session["done"] = i + 1

            # Non-beverage distractors are dropped entirely — same as main.py,
            # they are not a product a shelf report should ever mention.
            if is_non_beverage(gated):
                continue

            if gated == "low_confidence":
                status = "low_confidence"
            elif gated == "unknown_beverage":
                status = "unknown"
            else:
                status = "identified"

            # Share of shelf counts only confidently-identified beverages
            # (status identified/unknown) — mirrors main.py's bev_facings/bev_area,
            # low_confidence stays out of both numerator and denominator.
            if status != "low_confidence":
                facings[gated] += 1
                area_by_product[gated] += crop["area"]
                total_area += crop["area"]

            session["crops"].append({
                "id":         crop["name"],
                "url":        f"/api/crop/{session['id']}/{crop['name']}",
                "box":        [int(v) for v in crop["box"]],
                "area":       crop["area"],
                "predicted":  gated,
                "score":      round(score, 4),
                "status":     status,
            })

        total_facings = sum(facings.values())
        session["total_facings"] = total_facings
        session["share_of_shelf"] = [
            {
                "product": product,
                "facings": count,
                "share_by_facings": round(count / total_facings, 4) if total_facings else 0.0,
                "share_by_space": round(area_by_product[product] / total_area, 4) if total_area else 0.0,
            }
            for product, count in facings.most_common()
        ]

        session["stage"]  = "done"
        session["status"] = "ready"
    except Exception as e:
        session["status"] = "error"
        session["error"]  = f"{e.__class__.__name__}: {e}"
        traceback.print_exc()


# ── HTTP ────────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    server_version = "ShelfAPI/1.0"

    def log_message(self, fmt, *a):
        if self.server.verbose:
            super().log_message(fmt, *a)

    def _send(self, code, body, ctype="application/octet-stream", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json")

    def _error(self, code, message):
        self._json({"error": message}, code)

    def _file(self, path):
        path = Path(path)
        if not path.is_file():
            return self._error(404, f"Not found: {path}")
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._send(200, path.read_bytes(), ctype)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _json_body(self):
        raw = self._body()
        return json.loads(raw or b"{}")

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        url   = urlparse(self.path)
        route = url.path
        try:
            if route == "/api/state":
                return self._json({
                    "status": ENGINE.status,
                    "error":  ENGINE.error,
                    "model":  ENGINE.args.model,
                    "match_mode": ENGINE.args.match_mode,
                })

            if route.startswith("/api/crop/"):
                _, _, _, sid, crop_id = route.split("/", 4)
                return self._file(SESSION_DIR / sid / f"{crop_id}.jpg")

            if route.startswith("/api/session/"):
                sid = route.rsplit("/", 1)[-1]
                session = SESSIONS.get(sid)
                if session is None:
                    return self._error(404, "Unknown session.")
                return self._json(session)

            return self._error(404, "No such route.")
        except (ValueError, KeyError) as e:
            return self._error(400, str(e).strip("'"))
        except Exception as e:
            traceback.print_exc()
            return self._error(500, f"{e.__class__.__name__}: {e}")

    def do_POST(self):
        url   = urlparse(self.path)
        route = url.path
        try:
            if route == "/api/upload":
                return self._upload(url.query)
            if route == "/api/detect":
                return self._detect()
            return self._error(404, "No such route.")
        except (ValueError, KeyError) as e:
            return self._error(400, str(e).strip("'"))
        except Exception as e:
            traceback.print_exc()
            return self._error(500, f"{e.__class__.__name__}: {e}")

    def _require_ready(self):
        if ENGINE.status != "ready":
            raise RuntimeError(
                ENGINE.error or "Models are still loading — try again in a moment.")

    def _upload(self, query):
        from urllib.parse import parse_qs
        params = parse_qs(query)
        name = params.get("name", ["upload.jpg"])[0]
        name = re.sub(r"[^A-Za-z0-9._-]", "_", unquote(name))[-80:] or "upload.jpg"
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        dest  = UPLOAD_DIR / f"{stamp}-{name}"
        data  = self._body()
        if not data:
            return self._error(400, "Empty upload.")
        dest.write_bytes(data)
        return self._json({"path": str(dest.resolve().relative_to(ROOT)).replace("\\", "/")})

    def _detect(self):
        self._require_ready()
        body = self._json_body()
        image = (ROOT / unquote(body.get("image", ""))).resolve()
        if not image.is_relative_to(DATA_DIR.resolve()):
            raise ValueError("Path outside data/ is not served.")
        if not image.is_file():
            return self._error(400, f"No such image: {body.get('image')}")
        session = start_session(image, body.get("tta", True))
        return self._json({"session": session["id"]})


class APIServer(ThreadingHTTPServer):
    daemon_threads = True
    verbose = False

    def handle_error(self, request, client_address):
        exc = __import__("sys").exc_info()[1]
        if isinstance(exc, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


def serve(args):
    global ENGINE
    ENGINE = Engine(args)
    threading.Thread(target=ENGINE.warmup, daemon=True).start()

    httpd = APIServer((args.host, args.port), Handler)
    httpd.verbose = args.verbose
    print(f"\nShelf detection API on http://{args.host}:{args.port}   (Ctrl-C to stop)")
    print("Models load in the background; /api/state reports when it's ready.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    from src.classifier import (CONF_THRESH, MATCH_MODES, DEFAULT_MODE,
                                default_margin, default_threshold)

    p = argparse.ArgumentParser(description="Read-only shelf detection API for the web app")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8001)
    p.add_argument("--model", default="dino2", choices=["dino2", "resnet18"])
    p.add_argument("--match-mode", default=DEFAULT_MODE, choices=list(MATCH_MODES))
    p.add_argument("--conf-threshold", type=float, default=CONF_THRESH)
    p.add_argument("--margin-threshold", type=float, default=None)
    p.add_argument("--sim-threshold", type=float, default=None)
    p.add_argument("--verbose", action="store_true")
    _args = p.parse_args()
    if _args.sim_threshold is None:
        _args.sim_threshold = default_threshold(_args.match_mode)
    if _args.margin_threshold is None:
        _args.margin_threshold = default_margin(_args.match_mode)
    elif _args.margin_threshold <= 0:
        _args.margin_threshold = None
    serve(_args)
