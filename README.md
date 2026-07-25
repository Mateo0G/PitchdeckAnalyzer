# TEN Capital — Pitch Deck Analyzer

Upload a pitch deck PDF → the Claude API runs the Investor Conviction Ladder analysis →
a branded TEN Capital `.docx` comes back as a download. Deployable to Railway as a web app.

## Files

| File | Role |
|---|---|
| [app.py](app.py) | FastAPI web app — upload page, background jobs, progress polling, download |
| [analysis.py](analysis.py) | The four-call Claude pipeline; also runs standalone as a CLI |
| [schemas.py](schemas.py) | JSON schemas for the structured-output calls |
| [report_template.py](report_template.py) | Document structure and formatting — the branded `.docx` builder |
| [TEMPLATE_STRUCTURE.md](TEMPLATE_STRUCTURE.md) | Human-readable spec of the document and its fields |
| `TEN_Capital_logo_footer.png` | Footer logo — must ship with the app for the branded footer to render |

## How the analysis works

Four Claude API calls, each returning **validated JSON** (structured outputs) rather than prose,
so nothing has to be parsed out of free text. The deck rides along as a **cached document block**
in every call, so only the first request pays full price for it.

| # | Call | Produces |
|---|---|---|
| 1 | Data readiness | Section 1 — readiness matrix, per-stage PRESENT/PARTIAL/MISSING tables, P1/P2 gaps |
| 2 | Conviction ladder | Section 2 — the ten stage scores and narratives (call 1's findings are fed in as evidence) |
| 3 | Deck analysis | Section 2B — section-by-section strengths/weaknesses/recommendations, design notes, revised outline |
| 4 | Validation check | Section 3 — hallucination audit of calls 1–3 against the deck |

Model: `claude-opus-5`, adaptive thinking, `effort: high`, streamed. Runs about 4–8 minutes and
costs roughly $1–3 per deck depending on deck size.

**Guardrails between the model and the document.** Model output is reconciled against the
template's fixed rows before rendering — the ten stages and their required data points, the eleven
deck sections, the five design dimensions. A dropped, reordered, or reworded row is put back in
place (a missing data point renders as `MISSING`), so the document always has its full structure.
The conviction total is **computed** from the stage scores rather than taken from the model, and
the band label on the title-page banner comes from `CONVICTION_BANDS` in [analysis.py](analysis.py)
— edit those thresholds to change the wording.

## Run locally

```powershell
pip install -r requirements.txt
$env:ANTHROPIC_API_KEY = "sk-ant-..."     # from console.anthropic.com/settings/keys
uvicorn app:app --reload
```

Open http://127.0.0.1:8000.

Command line, no web app:

```powershell
python analysis.py "path\to\deck.pdf"
```

Preview the empty document layout without calling the API:

```powershell
python report_template.py        # writes _template_preview.docx
```

## Deploy to Railway

1. **Push this folder to a GitHub repo.** It needs `app.py`, `analysis.py`, `schemas.py`,
   `report_template.py`, `requirements.txt`, `Procfile`, `railway.json`, `.python-version`,
   and `TEN_Capital_logo_footer.png`.
2. **Railway → New Project → Deploy from GitHub repo**, and pick it. Nixpacks detects Python from
   `requirements.txt`; `railway.json` supplies the start command and the `/healthz` health check.
3. **Variables** (service → Variables):

   | Variable | Required | Purpose |
   |---|---|---|
   | `ANTHROPIC_API_KEY` | yes | Your key from the Claude console |
   | `APP_PASSWORD` | strongly recommended | Puts the whole app behind HTTP Basic auth |
   | `APP_USERNAME` | no | Basic-auth username (default `ten`) |
   | `MAX_CONCURRENT_JOBS` | no | Simultaneous analyses (default `2`) |
   | `JOB_TTL_MINUTES` | no | How long finished reports stay downloadable (default `180`) |
   | `JOBS_DIR` | no | Where uploads and reports are written (default: system temp) |

4. **Settings → Networking → Generate Domain** to get the public URL.

Set `APP_PASSWORD` before sharing the URL. Without it the app is open to anyone who finds it,
and every upload spends your API credit.

### Deployment notes

- **Uploads and reports are ephemeral.** Railway's filesystem resets on every deploy and restart,
  and jobs are held in memory, so a restart mid-analysis loses that job. Download the `.docx` when
  it's ready. If you want reports to survive restarts, attach a Railway volume and point `JOBS_DIR`
  at its mount path.
- **Uploaded decks are deleted** from the server as soon as the report is built.
- **Jobs run in the app process**, so a single Railway instance handles `MAX_CONCURRENT_JOBS` at a
  time; further uploads queue. Raising it raises memory use — each in-flight deck is held in memory
  as base64.
- **Deck size limit is 32 MB**, imposed by the API. Larger decks are rejected at upload with a
  clear message.
- The browser tab must stay open — it's what polls for progress and fetches the file.

## Changing the analysis

- **Document structure or formatting** → [report_template.py](report_template.py); the framework
  vocabularies (`CONVICTION_STAGES`, `DECK_SECTIONS`, `DESIGN_DIMENSIONS`, `HALLUCINATION_TYPES`)
  live there and drive the prompts, the schemas, and the rendered document together.
- **What the model is asked** → the prompt constants in [analysis.py](analysis.py).
- **Shape of the model's answer** → [schemas.py](schemas.py), kept in step with the template's
  data contract.
