"""Tailor: a CV helper. Start it with run.bat (Windows), ./run.sh (Mac, Linux)
or:  python app.py
"""

import os
import re
import sys
import threading
import time
import webbrowser
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

from core import ai, matcher, reader, tailor, word

FROZEN = getattr(sys, "frozen", False)
RES = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
HOME = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent


def load_env_file():
    env = HOME / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env_file()
KEY = os.environ.get("GEMINI_API_KEY", "").strip()
AI_OPTS = {"model": os.environ.get("TAILOR_GEMINI_MODEL", "").strip(),
           "base_url": os.environ.get("GEMINI_API_BASE", ai.GEMINI_URL).strip()}
PORT = int(os.environ.get("PORT", "5080"))
HOST = os.environ.get("HOST", "127.0.0.1")
# When Tailor is on a website, each visitor gets this many AI uses a day, so
# one person cannot use up the whole free allowance.
AI_PER_DAY = int(os.environ.get("AI_USES_PER_VISITOR_PER_DAY", "15"))

app = Flask(__name__, template_folder=str(RES / "templates"))
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
if os.environ.get("TRUST_PROXY") == "1":   # behind a host such as AWS App Runner or Render
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

_uses = {}
_uses_lock = threading.Lock()


def ai_allowed() -> bool:
    """Count one AI use for this visitor. False once they hit today's limit."""
    if HOST in ("127.0.0.1", "localhost"):
        return True   # on your own computer there is no limit
    day = int(time.time() // 86400)
    who = (request.remote_addr or "?", day)
    with _uses_lock:
        for k in [k for k in _uses if k[1] != day]:
            del _uses[k]
        if _uses.get(who, 0) >= AI_PER_DAY:
            return False
        _uses[who] = _uses.get(who, 0) + 1
    return True


LIMIT_NOTE = "You have used today's AI allowance on this site, so this was done without AI. It resets tomorrow."


def body():
    data = request.get_json(silent=True) or {}
    cv = tailor.normalise(data.get("cv") or {})
    job = str(data.get("job") or "")[:30000]
    use_ai = bool(data.get("use_ai")) and bool(KEY)
    return data, cv, job, use_ai


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/status")
def status():
    return jsonify({"ai": bool(KEY),
                    "styles": {k: {"label": v["label"], "about": v["about"]} for k, v in word.STYLES.items()},
                    "colours": word.COLOURS})


@app.get("/api/sample")
def sample():
    cv_text = (RES / "samples" / "sample-cv.txt").read_text(encoding="utf-8")
    job = (RES / "samples" / "sample-job.txt").read_text(encoding="utf-8")
    return jsonify({"cv": tailor.normalise(reader.parse_text(cv_text)), "job": job})


@app.post("/api/read")
def read_cv():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Please choose a file."}), 400
    try:
        text = reader.text_from_file(f.filename, f.read())
    except ValueError as err:
        return jsonify({"error": str(err)}), 400
    except Exception:
        return jsonify({"error": "That file could not be read. Try a .docx, .pdf or .txt file."}), 400
    if len(text.strip()) < 30:
        return jsonify({"error": "No text was found in that file. If it is a scanned PDF, "
                                 "try the Word version of your CV instead."}), 400
    note, used_ai = "", False
    cv = None
    if request.form.get("use_ai") == "1" and KEY and not ai_allowed():
        note = LIMIT_NOTE
    elif request.form.get("use_ai") == "1" and KEY:
        try:
            cv = tailor.normalise(ai.parse_cv(text, KEY, **AI_OPTS))
            used_ai = True
        except RuntimeError as err:
            note = f"{err} Your CV was read without AI instead, so please check every section."
    if cv is None:
        cv = tailor.normalise(reader.parse_text(text))
        if not note:
            note = "Your CV was read without AI. Please check every section below and fix anything that landed in the wrong place."
    return jsonify({"cv": cv, "note": note, "used_ai": used_ai})


@app.post("/api/match")
def match():
    _, cv, job, _ = body()
    if len(job.strip()) < 40:
        return jsonify({"error": "Please paste the full job description first."}), 400
    return jsonify(matcher.check(cv, job))


@app.post("/api/tailor")
def tailor_cv():
    _, cv, job, use_ai = body()
    if len(job.strip()) < 40:
        return jsonify({"error": "Please paste the full job description first."}), 400
    if not (cv["experience"] or cv["skills"] or cv["summary"]):
        return jsonify({"error": "Please add your CV first."}), 400
    note = ""
    result = None
    if use_ai and not ai_allowed():
        note = LIMIT_NOTE
        use_ai = False
    if use_ai:
        try:
            result = tailor.with_ai(cv, job, KEY, **AI_OPTS)
        except RuntimeError as err:
            note = f"{err} Your CV was tailored without AI instead."
    if result is None:
        result = tailor.offline(cv, job)
    result["note"] = note
    result["before"] = matcher.check(cv, job)
    result["after"] = matcher.check(result["cv"], job)
    return jsonify(result)


@app.post("/api/download")
def download():
    data, cv, _, _ = body()
    style = data.get("style") if data.get("style") in word.STYLES else "modern"
    colour = data.get("colour") if data.get("colour") in word.COLOURS else ""
    order = "education_first" if data.get("order") == "education_first" else "experience_first"
    file = word.build(cv, style, colour, order)
    name = re.sub(r"[^A-Za-z0-9]+", "_", cv.get("name") or "My").strip("_") or "My"
    return Response(file, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{name}_CV.docx"'})


@app.errorhandler(413)
def too_big(_):
    return jsonify({"error": "That file is too big. The limit is 8 MB."}), 413


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    return resp


if __name__ == "__main__":
    if HOST not in ("127.0.0.1", "localhost"):
        # On a website: use a proper web server, not Flask's test one.
        from waitress import serve
        print(f"Tailor is serving on {HOST}:{PORT}")
        serve(app, host=HOST, port=PORT, threads=8)
        sys.exit()
    url = f"http://localhost:{PORT}"
    print(f"\n  Tailor is running. Open {url} in your browser.\n  Press Ctrl+C to stop.\n")
    if os.environ.get("TAILOR_NO_BROWSER") != "1":
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host=HOST, port=PORT, debug=False)
