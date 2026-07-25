"""
TEN Capital — Pitch Deck Analyzer (web app)

Upload a pitch deck PDF, the Claude API runs the four-stage conviction analysis,
and the branded TEN Capital .docx comes back as a download.

Analysis takes several minutes, so uploads start a background job and the page
polls for progress rather than holding the request open.

Run locally:
    pip install -r requirements.txt
    $env:ANTHROPIC_API_KEY = "sk-ant-..."      # PowerShell
    uvicorn app:app --reload

Environment:
    ANTHROPIC_API_KEY   required — from console.anthropic.com/settings/keys
    APP_PASSWORD        optional — when set, the whole app sits behind
                        HTTP Basic auth (username `ten`, or set APP_USERNAME)
    JOBS_DIR            optional — where uploads and reports are written
    JOB_TTL_MINUTES     optional — how long finished reports stay downloadable
"""

from __future__ import annotations

import os
import re
import secrets
import tempfile
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from analysis import MAX_PDF_BYTES, PROGRESS_STEPS, AnalysisError, run_analysis

APP_USERNAME = os.getenv("APP_USERNAME", "ten")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
JOBS_DIR = Path(os.getenv("JOBS_DIR") or Path(tempfile.gettempdir()) / "pitchdeck-jobs")
JOB_TTL = timedelta(minutes=int(os.getenv("JOB_TTL_MINUTES", "180")))
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))

JOBS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="TEN Capital — Pitch Deck Analyzer")
_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT)
_basic = HTTPBasic(auto_error=False)


# --- Auth ---------------------------------------------------------------------


def require_auth(credentials: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    """HTTP Basic gate — active only when APP_PASSWORD is set."""
    if not APP_PASSWORD:
        return
    ok = credentials is not None and secrets.compare_digest(
        credentials.username, APP_USERNAME
    ) and secrets.compare_digest(credentials.password, APP_PASSWORD)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized",
            headers={"WWW-Authenticate": "Basic"},
        )


# --- Job tracking --------------------------------------------------------------


@dataclass
class Job:
    id: str
    company: str
    source: str
    state: str = "queued"  # queued | running | done | error
    step: int = 0
    message: str = "Queued"
    error: str = ""
    output: Path | None = None
    created: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "company": self.company,
            "source": self.source,
            "state": self.state,
            "step": self.step,
            "steps_total": len(PROGRESS_STEPS),
            "message": self.message,
            "error": self.error,
            "download": f"/jobs/{self.id}/download" if self.state == "done" else None,
        }


_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()


def _sweep_expired() -> None:
    """Drop finished jobs (and their files) once they age out."""
    cutoff = datetime.now(timezone.utc) - JOB_TTL
    with _jobs_lock:
        stale = [j for j in _jobs.values() if j.created < cutoff and j.state in ("done", "error")]
        for job in stale:
            _jobs.pop(job.id, None)
    for job in stale:
        folder = JOBS_DIR / job.id
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*"), reverse=True):
            path.unlink(missing_ok=True)
        folder.rmdir()


def _safe_name(name: str) -> str:
    """A filename that survives Windows, Linux, and Content-Disposition."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", name).strip(" .")
    return re.sub(r"\s+", " ", cleaned)[:80] or "Pitch Deck"


def _run_job(job: Job, pdf_path: Path) -> None:
    def progress(index: int, label: str) -> None:
        job.step, job.message = index, label

    job.state, job.message = "running", PROGRESS_STEPS[0]
    try:
        output = pdf_path.parent / f"{_safe_name(job.company)} - TEN Capital Conviction Analysis.docx"
        run_analysis(pdf_path, output, company_name=job.company, progress=progress)
        job.output = output
        job.state, job.step = "done", len(PROGRESS_STEPS)
        job.message = "Report ready"
    except AnalysisError as exc:
        job.state, job.error, job.message = "error", str(exc), "Analysis failed"
    except Exception as exc:  # surface a usable message, keep the trace in the logs
        traceback.print_exc()
        job.state, job.message = "error", "Analysis failed"
        job.error = f"{type(exc).__name__}: {exc}"
    finally:
        pdf_path.unlink(missing_ok=True)  # the deck is not ours to keep


# --- Routes --------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def index(_: None = Depends(require_auth)) -> HTMLResponse:
    return HTMLResponse(INDEX_HTML)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "api_key_configured": bool(os.getenv("ANTHROPIC_API_KEY"))}


@app.post("/analyze")
async def analyze(
    _: None = Depends(require_auth),
    deck: UploadFile = File(...),
    company: str = Form(""),
) -> JSONResponse:
    if not (deck.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Upload a PDF pitch deck.")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(
            503,
            "ANTHROPIC_API_KEY is not set on the server. Add it in the Railway service variables.",
        )

    _sweep_expired()

    job_id = uuid.uuid4().hex[:12]
    folder = JOBS_DIR / job_id
    folder.mkdir(parents=True, exist_ok=True)
    pdf_path = folder / _safe_name(Path(deck.filename).name)

    size = 0
    with pdf_path.open("wb") as handle:
        while chunk := await deck.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_PDF_BYTES:
                handle.close()
                pdf_path.unlink(missing_ok=True)
                folder.rmdir()
                raise HTTPException(
                    413, f"Deck exceeds the {MAX_PDF_BYTES // 1024 // 1024} MB limit the API accepts."
                )
            handle.write(chunk)

    job = Job(
        id=job_id,
        company=(company.strip() or pdf_path.stem),
        source=pdf_path.name,
    )
    with _jobs_lock:
        _jobs[job_id] = job
    _executor.submit(_run_job, job, pdf_path)
    return JSONResponse(job.as_dict(), status_code=202)


@app.get("/jobs/{job_id}")
def job_status(job_id: str, _: None = Depends(require_auth)) -> dict:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown or expired job.")
    return job.as_dict()


@app.get("/jobs/{job_id}/download")
def job_download(job_id: str, _: None = Depends(require_auth)) -> FileResponse:
    job = _jobs.get(job_id)
    if job is None or job.state != "done" or job.output is None or not job.output.exists():
        raise HTTPException(404, "No report available for that job.")
    return FileResponse(
        job.output,
        filename=job.output.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# --- Front end -----------------------------------------------------------------

INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TEN Capital — Pitch Deck Analyzer</title>
<style>
  :root {
    --navy: #1F3864; --blue: #2E75B6; --gold: #FFC000;
    --ink: #1b1b1b; --muted: #666; --line: #dfe3ea; --bg: #f5f7fa;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font: 15px/1.55 "Segoe UI", Arial, system-ui, sans-serif;
  }
  .wrap { max-width: 720px; margin: 0 auto; padding: 48px 20px 64px; }
  header { text-align: center; margin-bottom: 32px; }
  h1 { margin: 0; font-size: 26px; letter-spacing: .12em; color: var(--navy); }
  .sub { color: var(--blue); font-size: 15px; margin-top: 6px; }
  .card {
    background: #fff; border: 1px solid var(--line); border-radius: 10px;
    padding: 28px; box-shadow: 0 1px 3px rgba(31,56,100,.06);
  }
  label { display: block; font-weight: 600; font-size: 13px; color: var(--navy); margin-bottom: 6px; }
  input[type=text], input[type=file] {
    width: 100%; padding: 10px 12px; border: 1px solid var(--line);
    border-radius: 6px; font: inherit; background: #fff;
  }
  .field { margin-bottom: 18px; }
  .hint { color: var(--muted); font-size: 12.5px; margin-top: 6px; }
  button {
    width: 100%; padding: 12px 16px; border: 0; border-radius: 6px;
    background: var(--navy); color: #fff; font: 600 15px inherit; cursor: pointer;
  }
  button:disabled { background: #9aa5b8; cursor: not-allowed; }
  #status { margin-top: 24px; display: none; }
  .bar { height: 8px; background: #e8ecf3; border-radius: 4px; overflow: hidden; }
  .bar > i { display: block; height: 100%; width: 0; background: var(--blue); transition: width .4s ease; }
  .steps { list-style: none; margin: 16px 0 0; padding: 0; }
  .steps li { padding: 5px 0 5px 26px; position: relative; color: var(--muted); font-size: 14px; }
  .steps li::before {
    content: "○"; position: absolute; left: 4px; color: #c3cbd9;
  }
  .steps li.done { color: var(--ink); }
  .steps li.done::before { content: "●"; color: #375623; }
  .steps li.active { color: var(--navy); font-weight: 600; }
  .steps li.active::before { content: "●"; color: var(--gold); }
  .done-box, .error-box { margin-top: 20px; padding: 16px; border-radius: 6px; font-size: 14px; }
  .done-box { background: #E2EFDA; color: #375623; }
  .error-box { background: #FFCCCC; color: #C00000; white-space: pre-wrap; }
  a.download {
    display: inline-block; margin-top: 10px; padding: 10px 18px; border-radius: 6px;
    background: var(--gold); color: var(--navy); font-weight: 700; text-decoration: none;
  }
  footer { text-align: center; color: var(--muted); font-size: 12px; margin-top: 28px; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>TEN CAPITAL</h1>
    <div class="sub">Investor Conviction Ladder — Pitch Deck Analyzer</div>
  </header>

  <div class="card">
    <form id="form">
      <div class="field">
        <label for="company">Company name</label>
        <input type="text" id="company" name="company" placeholder="Leave blank to use the file name">
      </div>
      <div class="field">
        <label for="deck">Pitch deck (PDF)</label>
        <input type="file" id="deck" name="deck" accept="application/pdf" required>
        <div class="hint">Up to 32 MB. The deck is deleted from the server once the report is built.</div>
      </div>
      <button type="submit" id="go">Run conviction analysis</button>
    </form>

    <div id="status">
      <div class="bar"><i id="fill"></i></div>
      <ul class="steps" id="steps"></ul>
      <div id="result"></div>
    </div>
  </div>

  <footer>Analysis runs on Claude Opus 5 · typically 4–8 minutes · keep this tab open</footer>
</div>

<script>
const STEPS = %%STEPS%%;
const form = document.getElementById('form');
const statusBox = document.getElementById('status');
const stepsList = document.getElementById('steps');
const fill = document.getElementById('fill');
const result = document.getElementById('result');
const go = document.getElementById('go');

function renderSteps(step, state) {
  stepsList.innerHTML = STEPS.map((label, i) => {
    let cls = '';
    if (state === 'done' || i < step) cls = 'done';
    else if (i === step && state === 'running') cls = 'active';
    return `<li class="${cls}">${label}</li>`;
  }).join('');
  const pct = state === 'done' ? 100 : Math.round((step / STEPS.length) * 100);
  fill.style.width = pct + '%';
}

async function poll(id) {
  const res = await fetch(`/jobs/${id}`);
  if (!res.ok) throw new Error('Lost track of the job — reload and try again.');
  const job = await res.json();
  renderSteps(job.step, job.state);

  if (job.state === 'done') {
    result.innerHTML = `<div class="done-box">Report ready.<br>
      <a class="download" href="${job.download}">Download .docx</a></div>`;
    go.disabled = false;
    go.textContent = 'Run another analysis';
    return;
  }
  if (job.state === 'error') {
    result.innerHTML = `<div class="error-box"><strong>Analysis failed.</strong>\\n${job.error}</div>`;
    go.disabled = false;
    go.textContent = 'Try again';
    return;
  }
  setTimeout(() => poll(id).catch(showError), 3000);
}

function showError(err) {
  result.innerHTML = `<div class="error-box">${err.message}</div>`;
  go.disabled = false;
  go.textContent = 'Try again';
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  go.disabled = true;
  go.textContent = 'Analyzing…';
  statusBox.style.display = 'block';
  result.innerHTML = '';
  renderSteps(0, 'running');

  try {
    const res = await fetch('/analyze', { method: 'POST', body: new FormData(form) });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(detail.detail || 'Upload failed.');
    }
    const job = await res.json();
    poll(job.id).catch(showError);
  } catch (err) {
    showError(err);
  }
});
</script>
</body>
</html>
""".replace("%%STEPS%%", str(PROGRESS_STEPS).replace("'", '"'))
