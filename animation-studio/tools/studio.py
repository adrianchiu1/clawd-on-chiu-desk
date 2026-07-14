#!/usr/bin/env python3
"""Clawd Animation Studio — the interactive Idea Card, in your browser.

Run this, and a kid-friendly page opens where the director fills in the four
Idea Card questions, names the dance, and presses the big button. The studio:

  1. saves the answers as a spec file    → output/specs/<name>.json
  2. builds the AI prompt                → output/<name>.prompt.txt
  3. if the `claude` CLI is installed, generates the animation and shows it
     dancing right on the page; otherwise it shows the prompt to copy into
     claude.ai and a box to paste the answer back — same result.

Everything stays on this computer: the server binds to 127.0.0.1 only.
Python 3 standard library only — no installs.

Usage:
    python3 tools/studio.py            # http://127.0.0.1:8787
    python3 tools/studio.py --port 9000
    python3 tools/studio.py --no-browser
"""

import argparse
import json
import re
import shutil
import subprocess
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_prompt import STUDIO_ROOT, build_prompt, load_grammar  # noqa: E402
from claude_animate import extract_svg, sanity_check  # noqa: E402

OUTPUT_DIR = STUDIO_ROOT / "output"
SPECS_DIR = OUTPUT_DIR / "specs"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
CLAUDE_TIMEOUT = 300

# jobId -> {"state": "running"|"done"|"error", "svgUrl": str, "error": str,
#           "warnings": [str], "file": str}
JOBS = {}
JOBS_LOCK = threading.Lock()


def list_grammars():
    out = []
    gdir = STUDIO_ROOT / "grammars"
    for p in sorted(gdir.iterdir()):
        if (p / "grammar.json").exists():
            try:
                meta = json.loads((p / "grammar.json").read_text(encoding="utf-8"))
                out.append({"id": p.name, "name": meta.get("name", p.name)})
            except (OSError, json.JSONDecodeError):
                continue
    return out


def assemble_description(spec):
    parts = [
        f"Action: {spec['action'].strip()}",
        f"Body mechanics: {spec['body'].strip()}",
        f"Eyes: {spec['eyes'].strip()}",
        f"Effects: {spec['effects'].strip()}",
    ]
    if spec.get("speed"):
        parts.append(f"Overall speed: {spec['speed']}")
    if spec.get("mood"):
        parts.append(f"Mood: {spec['mood']}")
    return ". ".join(parts) + "."


def save_spec(spec, description):
    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    record = dict(spec)
    record["description"] = description
    record["created"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path = SPECS_DIR / f"{spec['name']}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def save_svg(grammar, name, svg_text):
    prefix = grammar["meta"].get("filePrefix", "anim")
    filename = f"{prefix}-{name}.svg"
    out = OUTPUT_DIR / filename
    out.write_text(svg_text if svg_text.endswith("\n") else svg_text + "\n", encoding="utf-8")
    return filename


def run_claude_job(job_id, grammar, name, prompt):
    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True, text=True, timeout=CLAUDE_TIMEOUT,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "claude CLI failed")
        svg = extract_svg(result.stdout)
        if not svg:
            raise RuntimeError("no <svg> found in the AI's answer — try again")
        warnings = sanity_check(svg)
        filename = save_svg(grammar, name, svg)
        with JOBS_LOCK:
            JOBS[job_id] = {"state": "done", "svgUrl": f"/output/{filename}",
                            "file": f"animation-studio/output/{filename}", "warnings": warnings}
    except Exception as err:  # noqa: BLE001 — report anything to the page
        with JOBS_LOCK:
            JOBS[job_id] = {"state": "error", "error": str(err)}


class StudioHandler(BaseHTTPRequestHandler):
    server_version = "ClawdStudio/1.0"

    # ── helpers ──
    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > 2_000_000:
            return None
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def log_message(self, fmt, *args):  # quieter console
        pass

    # ── routes ──
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self.send_html(render_page())
        if parsed.path == "/api/status":
            job_id = (parse_qs(parsed.query).get("job") or [""])[0]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if not job:
                return self.send_json({"state": "error", "error": "unknown job"}, 404)
            return self.send_json(job)
        if parsed.path.startswith("/output/"):
            return self.serve_svg(parsed.path[len("/output/"):])
        self.send_json({"error": "not found"}, 404)

    def serve_svg(self, rel):
        # only .svg files that live directly in output/
        if "/" in rel or not rel.endswith(".svg"):
            return self.send_json({"error": "not found"}, 404)
        target = (OUTPUT_DIR / rel).resolve()
        if target.parent != OUTPUT_DIR.resolve() or not target.exists():
            return self.send_json({"error": "not found"}, 404)
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        # belt & braces: even though sanity_check flags scripts, forbid them
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'unsafe-inline'")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/create":
            return self.api_create()
        if parsed.path == "/api/paste":
            return self.api_paste()
        self.send_json({"error": "not found"}, 404)

    def api_create(self):
        data = self.read_json_body()
        if not data:
            return self.send_json({"error": "bad request"}, 400)
        name = str(data.get("name", "")).strip()
        if not NAME_RE.fullmatch(name):
            return self.send_json(
                {"error": "Name must be small letters/numbers with dashes, like dance-spin"}, 400)
        for field in ("action", "body", "eyes", "effects"):
            if not str(data.get(field, "")).strip():
                return self.send_json({"error": f"Please fill in the '{field}' box!"}, 400)
        try:
            grammar = load_grammar(str(data.get("grammar", "rect-crab")))
        except SystemExit as err:
            return self.send_json({"error": str(err)}, 400)

        spec = {k: str(data.get(k, "")).strip()
                for k in ("name", "grammar", "action", "body", "eyes", "effects", "speed", "mood")}
        description = assemble_description(spec)
        save_spec(spec, description)

        example_svg = ""
        if grammar["example_path"] and Path(grammar["example_path"]).exists():
            example_svg = Path(grammar["example_path"]).read_text(encoding="utf-8")
        prompt = build_prompt(grammar, name, description, example_svg)
        (OUTPUT_DIR / f"{name}.prompt.txt").write_text(prompt, encoding="utf-8")

        if data.get("forcePaste") or not shutil.which("claude"):
            prefix = grammar["meta"].get("filePrefix", "anim")
            return self.send_json({"mode": "paste", "prompt": prompt,
                                   "name": name, "prefix": prefix})

        job_id = uuid.uuid4().hex
        with JOBS_LOCK:
            JOBS[job_id] = {"state": "running"}
        threading.Thread(target=run_claude_job,
                         args=(job_id, grammar, name, prompt), daemon=True).start()
        return self.send_json({"mode": "claude", "job": job_id})

    def api_paste(self):
        data = self.read_json_body()
        if not data:
            return self.send_json({"error": "bad request"}, 400)
        name = str(data.get("name", "")).strip()
        if not NAME_RE.fullmatch(name):
            return self.send_json({"error": "bad name"}, 400)
        try:
            grammar = load_grammar(str(data.get("grammar", "rect-crab")))
        except SystemExit as err:
            return self.send_json({"error": str(err)}, 400)
        svg = extract_svg(str(data.get("svg", "")))
        if not svg:
            return self.send_json(
                {"error": "That doesn't look like SVG — copy the AI's whole answer and try again."}, 400)
        warnings = sanity_check(svg)
        filename = save_svg(grammar, name, svg)
        return self.send_json({"svgUrl": f"/output/{filename}",
                               "file": f"animation-studio/output/{filename}",
                               "warnings": warnings})


def render_page():
    options = "".join(
        f'<option value="{g["id"]}">{g["name"]}</option>' for g in list_grammars()
    )
    return PAGE_HTML.replace("__GRAMMAR_OPTIONS__", options)


PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clawd Animation Studio 🦀</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: "Segoe UI", "Helvetica Neue", Arial, "Noto Sans CJK SC",
         "PingFang SC", "Microsoft YaHei", sans-serif;
         background: #fdf3ee; color: #2b2b2b; margin: 0; padding: 24px;
         display: flex; justify-content: center; }
  main { width: 100%; max-width: 640px; }
  h1 { color: #b5482a; font-size: 30px; margin: 0 0 2px; }
  .sub { color: #8a7c73; margin: 0 0 22px; }
  .card { background: #fff; border: 3px solid #de886d; border-radius: 16px;
          padding: 20px 22px; margin-bottom: 18px;
          box-shadow: 0 4px 0 rgba(222,136,109,.25); }
  label { display: block; font-weight: 700; margin: 14px 0 4px; font-size: 15px; }
  label .zh { font-weight: 400; color: #8a7c73; }
  input[type=text], textarea, select {
    width: 100%; border: 2px solid #e6c9bc; border-radius: 10px;
    padding: 9px 11px; font-size: 15px; font-family: inherit; background: #fffdfb; }
  textarea { min-height: 52px; resize: vertical; }
  input:focus, textarea:focus, select:focus { outline: none; border-color: #de886d; }
  .hint { font-size: 12.5px; color: #a08d82; margin-top: 3px; }
  .choices { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }
  .choices input { display: none; }
  .choices span { display: inline-block; border: 2px solid #e6c9bc; border-radius: 999px;
                  padding: 5px 14px; cursor: pointer; font-size: 14px; background: #fffdfb; }
  .choices input:checked + span { background: #de886d; border-color: #de886d; color: #fff; }
  button.big { width: 100%; margin-top: 20px; background: #de886d; color: #fff;
               font-size: 20px; font-weight: 800; border: none; border-radius: 14px;
               padding: 14px; cursor: pointer; box-shadow: 0 4px 0 #b5482a; }
  button.big:active { transform: translateY(3px); box-shadow: 0 1px 0 #b5482a; }
  button.small { background: #fff; color: #b5482a; border: 2px solid #de886d;
                 border-radius: 10px; padding: 8px 14px; font-size: 14px;
                 font-weight: 700; cursor: pointer; margin: 6px 6px 0 0; }
  #stage { text-align: center; }
  #stage img { width: 100%; max-width: 440px; background: #fff;
               border: 3px dashed #de886d; border-radius: 16px; }
  .spinner { font-size: 44px; animation: wiggle 1s infinite ease-in-out; display: inline-block; }
  @keyframes wiggle { 0%,100% { transform: rotate(-12deg); } 50% { transform: rotate(12deg); } }
  .error { background: #fdecec; border: 2px solid #e08a8a; border-radius: 10px;
           padding: 10px 14px; color: #8c2f2f; margin-top: 12px; }
  .warn { background: #fdf6e0; border: 2px solid #d9a406; border-radius: 10px;
          padding: 8px 12px; font-size: 13.5px; margin-top: 10px; text-align: left; }
  pre { background: #f3f3f3; border-radius: 10px; padding: 12px; font-size: 12px;
        max-height: 260px; overflow: auto; text-align: left; white-space: pre-wrap; }
  .filepath { font-size: 12.5px; color: #8a7c73; margin-top: 8px; word-break: break-all; }
  .hidden { display: none; }
</style>
</head>
<body>
<main>
  <h1>🦀 Clawd Animation Studio</h1>
  <p class="sub">You are the director. Fill in the card — the AI is your artist!
    你是导演，填好卡片，AI 是你的画家！</p>

  <form class="card" id="ideaCard">
    <label>Character family <span class="zh">角色家族</span></label>
    <select id="grammar">__GRAMMAR_OPTIONS__</select>

    <label>Dance name <span class="zh">舞蹈名字</span></label>
    <input type="text" id="name" placeholder="dance-spin" autocomplete="off">
    <div class="hint">small letters and dashes only — we fix it as you type · 只用小写字母和“-”</div>

    <label>1. Action — what is Clawd doing? <span class="zh">动作——他在做什么？</span></label>
    <textarea id="action" placeholder="Clawd is doing a super spin dance..."></textarea>

    <label>2. Body — how does his body move? <span class="zh">身体——身体怎么动？</span></label>
    <textarea id="body" placeholder="He sways side to side and his claws snap fast..."></textarea>

    <label>3. Eyes — what do his eyes do? <span class="zh">眼睛——眼睛在做什么？</span></label>
    <textarea id="eyes" placeholder="Squeezed shut and happy, blinking sometimes..."></textarea>

    <label>4. Effects — what appears around him? <span class="zh">特效——周围出现什么？</span></label>
    <textarea id="effects" placeholder="Yellow sparkles pop and confetti falls..."></textarea>

    <label>Speed <span class="zh">速度</span></label>
    <div class="choices" id="speed">
      <label><input type="radio" name="speed" value="slow"><span>slow 慢</span></label>
      <label><input type="radio" name="speed" value="medium" checked><span>medium 中</span></label>
      <label><input type="radio" name="speed" value="very fast"><span>FAST! 快！</span></label>
    </div>

    <label>Mood <span class="zh">心情</span></label>
    <div class="choices" id="mood">
      <label><input type="radio" name="mood" value="happy" checked><span>happy 开心</span></label>
      <label><input type="radio" name="mood" value="silly"><span>silly 搞怪</span></label>
      <label><input type="radio" name="mood" value="sleepy"><span>sleepy 想睡</span></label>
      <label><input type="radio" name="mood" value="excited"><span>excited 激动</span></label>
    </div>

    <button class="big" type="submit">🎬 Make it dance! 让它跳舞！</button>
    <div id="formError" class="error hidden"></div>
  </form>

  <div class="card hidden" id="stage"></div>
</main>

<script>
const $ = (id) => document.getElementById(id);
const stage = $("stage");
const form = $("ideaCard");

$("name").addEventListener("input", (e) => {
  e.target.value = e.target.value.toLowerCase()
    .replace(/[\\s_]+/g, "-").replace(/[^a-z0-9-]/g, "").replace(/-{2,}/g, "-");
});

function pick(groupId) {
  const el = document.querySelector(`#${groupId} input:checked`);
  return el ? el.value : "";
}
function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }
function setStage(html) { stage.innerHTML = html; show(stage); stage.scrollIntoView({behavior: "smooth"}); }

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hide($("formError"));
  const payload = {
    name: $("name").value.trim().replace(/^-+|-+$/g, ""),
    grammar: $("grammar").value,
    action: $("action").value, body: $("body").value,
    eyes: $("eyes").value, effects: $("effects").value,
    speed: pick("speed"), mood: pick("mood"),
  };
  $("name").value = payload.name;
  const res = await fetch("/api/create", { method: "POST",
    headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
  const data = await res.json();
  if (!res.ok) {
    $("formError").textContent = data.error || "Something went wrong.";
    show($("formError"));
    return;
  }
  if (data.mode === "claude") pollJob(data.job);
  else showPasteFlow(data);
});

function pollJob(jobId) {
  setStage(`<div class="spinner">🦀</div>
    <p><strong>Clawd is learning your dance…</strong><br>
    Clawd 正在学你的舞蹈…<br>
    <span class="hint">this takes about a minute 大约需要一分钟</span></p>`);
  const timer = setInterval(async () => {
    const res = await fetch(`/api/status?job=${jobId}`);
    const job = await res.json();
    if (job.state === "running") return;
    clearInterval(timer);
    if (job.state === "done") showResult(job);
    else setStage(`<div class="error">😢 ${job.error}</div>
      <button class="small" onclick="location.reload()">Try again 再试一次</button>`);
  }, 2000);
}

function showResult(job) {
  const warns = (job.warnings || []).map(w => `<div class="warn">⚠️ ${w}</div>`).join("");
  setStage(`
    <h2>🎉 Your dance! 你的舞蹈！</h2>
    <img src="${job.svgUrl}?t=${Date.now()}" alt="your animation">
    ${warns}
    <div class="filepath">Saved at 已保存在: <code>${job.file}</code></div>
    <button class="small" onclick="hide(stage); form.scrollIntoView({behavior:'smooth'})">
      🎬 Change it and try again 改一改再来一次</button>
    <button class="small" onclick="window.open('${job.svgUrl}','_blank')">
      🔍 Open big 放大看</button>`);
}

function showPasteFlow(data) {
  setStage(`
    <h2>Almost there! 就快好了！</h2>
    <p>Grown-up: copy this prompt, paste it into <strong>claude.ai</strong>,
    then paste the AI's whole answer below.<br>
    大人：复制这段提示词，粘贴到 claude.ai，再把 AI 的完整回答粘贴到下面。</p>
    <button class="small" id="copyBtn">📋 Copy the prompt 复制提示词</button>
    <pre id="promptBox"></pre>
    <textarea id="pasteBox" placeholder="Paste the AI's answer here... 把 AI 的回答粘贴到这里..."
      style="min-height:110px"></textarea>
    <button class="small" id="pasteGo">✅ Show my dance! 看我的舞蹈！</button>
    <div id="pasteError" class="error hidden"></div>`);
  $("promptBox").textContent = data.prompt;
  $("copyBtn").onclick = () => navigator.clipboard.writeText(data.prompt)
    .then(() => $("copyBtn").textContent = "✅ Copied! 已复制！");
  $("pasteGo").onclick = async () => {
    hide($("pasteError"));
    const res = await fetch("/api/paste", { method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ name: data.name, grammar: $("grammar").value,
                             svg: $("pasteBox").value }) });
    const out = await res.json();
    if (!res.ok) { $("pasteError").textContent = out.error; show($("pasteError")); return; }
    showResult(out);
  };
}
</script>
</body>
</html>
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--no-browser", action="store_true", help="don't auto-open the browser")
    args = parser.parse_args(argv)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), StudioHandler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"🦀 Clawd Animation Studio is open at {url}")
    if shutil.which("claude"):
        print("   claude CLI found — one-click generation is ON")
    else:
        print("   claude CLI not found — the page will use the copy-paste flow")
    print("   Press Ctrl+C to close the studio.")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStudio closed. Bye! 👋")


if __name__ == "__main__":
    main()
