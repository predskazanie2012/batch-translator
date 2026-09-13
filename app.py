"""
Batch Translator — Flask Web App
Запуск: python app.py   →  откроется http://127.0.0.1:5100
"""

import json
import os
import queue
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_file

_ROOT_TB = Path(__file__).resolve().parent
_AI_TB = _ROOT_TB
if str(_AI_TB) not in sys.path:
    sys.path.insert(0, str(_AI_TB))
from env_loader import load_env_stack

load_env_stack(_ROOT_TB)

app = Flask(__name__)

from local_access import protect_flask
protect_flask(app)


UPLOAD_DIR = Path(tempfile.gettempdir()) / "bt_uploads"
OUTPUT_DIR = Path(tempfile.gettempdir()) / "bt_output"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

_progress_q: queue.Queue  = queue.Queue()
_msg_buffer:  list        = []          # full history of current job
_new_msg_evt: threading.Event = threading.Event()
_stop_flag    = threading.Event()
_job_running  = threading.Lock()

GC_CREDS  = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
DEEPL_KEY = os.environ.get("DEEPL_API_KEY", "")


# ── Routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template(
        "index.html",
        gc_creds=GC_CREDS,
        deepl_key_hint=DEEPL_KEY[:8] + "…" if DEEPL_KEY else "",
    )


@app.route("/api/upload", methods=["POST"])
def upload():
    for f in UPLOAD_DIR.iterdir():
        try: f.unlink()
        except Exception: pass

    files = request.files.getlist("files")
    saved = []
    for f in files:
        if not f.filename:
            continue
        dest = UPLOAD_DIR / Path(f.filename).name
        f.save(str(dest))
        saved.append({"name": f.filename, "size": dest.stat().st_size})

    return jsonify({"count": len(saved), "files": saved})


@app.route("/api/translate", methods=["POST"])
def translate():
    if _job_running.locked():
        return jsonify({"error": "Уже выполняется перевод"}), 409

    data = request.get_json()

    # Flush old progress messages and clear buffer
    _msg_buffer.clear()
    _new_msg_evt.clear()
    while not _progress_q.empty():
        try: _progress_q.get_nowait()
        except queue.Empty: break

    _stop_flag.clear()
    t = threading.Thread(target=_run_job, args=(data,), daemon=True)
    t.start()
    return jsonify({"status": "started"})


@app.route("/api/progress")
def progress():
    def stream():
        # Replay buffered messages first (handles reconnects gracefully)
        cursor = 0
        while True:
            # Drain all buffered messages
            while cursor < len(_msg_buffer):
                msg = _msg_buffer[cursor]
                cursor += 1
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                if msg.get("type") in ("done", "stopped", "error"):
                    return

            # Wait for next message (long timeout — translations can be slow)
            _new_msg_evt.clear()
            signalled = _new_msg_evt.wait(timeout=60)
            if not signalled:
                # Keep-alive ping so the connection doesn't time out
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/stop", methods=["POST"])
def stop():
    _stop_flag.set()
    return jsonify({"status": "stopping"})


@app.route("/api/download")
def download():
    zip_path = Path(tempfile.gettempdir()) / "bt_translations.zip"
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for f in OUTPUT_DIR.rglob("*"):
            if f.is_file():
                zf.write(str(f), str(f.relative_to(OUTPUT_DIR)))
    return send_file(
        str(zip_path),
        as_attachment=True,
        download_name="translations.zip",
    )


# ── Job worker ───────────────────────────────────────────────────────────

def _pq(msg: dict):
    _msg_buffer.append(msg)
    _progress_q.put(msg)
    _new_msg_evt.set()


def _run_job(data: dict):
    with _job_running:
        from core import BatchTranslator

        engine   = data.get("engine", "google_cloud")
        langs    = data.get("langs", [])
        fmt      = data.get("fmt", "docx")
        src      = data.get("src") or None
        gc_creds = data.get("gc_creds") or GC_CREDS or None
        _dl_raw  = data.get("deepl_key") or ""
        dl_key   = (DEEPL_KEY if "\u2026" in _dl_raw else _dl_raw) or DEEPL_KEY or None

        # Clear output
        for f in OUTPUT_DIR.rglob("*"):
            if f.is_file():
                try: f.unlink()
                except Exception: pass

        files = [f for f in UPLOAD_DIR.iterdir() if f.is_file()]
        total = len(files) * len(langs)

        _pq({"type": "log", "text": "⚙  Инициализация движка перевода...", "tag": "info"})
        try:
            tr = BatchTranslator(engine=engine, gc_credentials=gc_creds, deepl_key=dl_key)
            tr.init()
            _pq({"type": "log", "text": "✓  Движок готов", "tag": "ok"})
        except Exception as e:
            _pq({"type": "log", "text": f"✗  Ошибка инициализации: {e}", "tag": "err"})
            _pq({"type": "done", "success": 0, "errors": 1})
            return

        done = errors = 0
        t0 = time.time()

        for fp in files:
            if _stop_flag.is_set():
                break
            for lc in langs:
                if _stop_flag.is_set():
                    break
                try:
                    tr.translate_file(str(fp), lc, fmt, str(OUTPUT_DIR), src)
                    done += 1
                    elapsed = time.time() - t0
                    per     = elapsed / done
                    eta_s   = int(per * (total - done))
                    eta = f"{eta_s//60}м {eta_s%60}с" if eta_s > 60 else f"{eta_s}с"
                    _pq({
                        "type": "progress", "done": done, "total": total,
                        "eta": eta, "text": f"✓  {fp.name}  →  {lc}", "ok": True,
                    })
                except Exception as e:
                    errors += 1
                    done   += 1
                    _pq({
                        "type": "progress", "done": done, "total": total,
                        "eta": "", "text": f"✗  {fp.name} [{lc}] — {e}", "ok": False,
                    })

        if _stop_flag.is_set():
            _pq({"type": "stopped"})
        else:
            tag = "ok" if not errors else "warn"
            _pq({"type": "log",
                 "text": f"{'✅' if not errors else '⚠'}  Готово: {done-errors} успешно, {errors} ошибок",
                 "tag": tag})
            _pq({"type": "done", "success": done - errors, "errors": errors})


# ── Entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import webbrowser

    def _open_browser():
        time.sleep(1.4)
        webbrowser.open("http://127.0.0.1:5100")

    threading.Thread(target=_open_browser, daemon=True).start()
    print("  Batch Translator zapushchen ->  http://127.0.0.1:5100")
    app.run(host="127.0.0.1", port=5100, debug=False, threaded=True)
