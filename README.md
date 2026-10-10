# Certify — Bulk Certificate Generator

Certify is a web app for creating personalized certificates in batches. You can enter recipients manually or import them from a CSV file, submit a batch, follow its progress, and download the finished certificates as PDFs or as a ZIP file.

I built this project to practise the full flow of a small web application: a React frontend, a FastAPI backend, background processing, database persistence, and PDF generation. The dashboard and job pages read from the API, so the status and counts shown in the UI come from stored data rather than hard-coded demo values.

The simplest way to run it locally is with SQLite and the included polling worker. A Docker Compose setup for PostgreSQL, Redis, and Celery is also included, but that setup still needs to be tested in an environment with Docker available.

## Where to start

* [Windows PowerShell setup](#windows-powershell-setup)
* [Docker Compose setup](#docker-compose-setup-provided-not-executed-in-this-environment)
* [API request example](#example-request)
* [Tests and verification evidence](VERIFICATION.md)
* [Architecture and flow](#architecture-and-flow)
* [Security and known limitations](#storage-security-and-operations)

## What it can do

* Dashboard with persisted aggregate metrics and recent jobs.
* Guided batch form, manual rows, CSV upload/paste, sample CSV, editable import preview, field validation and confirmation dialog.
* Job history with search, status filtering and pagination.
* Job detail with actual progress, timestamps, recipient filters, PDF downloads and real PDF preview.
* One reusable landscape certificate design with embedded font, escaped text and long-text wrapping/shrinking.
* Persistent acceptance, idempotency keys, isolated failures, bounded transient filesystem retries and stale-job recovery.
* ZIP downloads contain successful PDFs only; terminal-job archives are cached on disk.
* There is no login, email delivery, template editor, or manual retry endpoint yet. This project is intended for local demonstration and development, not as a production-ready multi-user service.

## Tech stack

React 19, strict TypeScript, Vite, Tailwind CSS 4, React Router, TanStack Query, React Hook Form, Zod, Lucide and Radix Dialog. Reusable accessible components are in `frontend/src/components/ui.tsx` rather than a full shadcn installation.

Python 3.11+, FastAPI, Pydantic, SQLAlchemy 2, Alembic, PostgreSQL, Celery/Redis, ReportLab, Pytest/HTTPX. SQLite plus a separate polling worker is the tested service-free local alternative. Direct Python dependencies are pinned in requirements.txt; npm has a complete package-lock.json. Use Node 22.12+ or Node 24.

## How it works

1. The browser validates fields and requires correction of every invalid row before submitting one JSON batch.
2. FastAPI validates job-level input and inserts the job and all recipient records in one transaction. It returns HTTP 201 without generating certificates.
3. The committed `queued` job row is the durable work record. A Celery Beat dispatcher scans queued or expired processing jobs every 10 seconds and publishes job IDs. It never sees uncommitted rows. This avoids a fragile commit-then-enqueue gap without a separate outbox table.
4. A worker atomically claims a job using an expiring lease and token. It processes recipients sequentially, committing status before and after each PDF. Default Celery concurrency is two jobs, not one task per recipient.
5. PDF writes use a temporary file and atomic replacement. Recipient UUIDs determine filenames; certificate UUIDs are persisted before rendering, so crash recovery reuses identifiers.
6. Successful recipient records retain certificate ID and storage key. Failures retain a safe code/message. Job totals and progress are derived from grouped recipient records, not duplicated counters.
7. The browser polls active detail pages every two seconds and stops when terminal. Dashboard/history refresh every five seconds. Closing the browser does not interrupt processing.
8. Downloads resolve only server-generated storage keys, check recipient status, parent job existence and file existence. Archives are generated on disk, not by loading every PDF into RAM.

This keeps certificate generation out of the HTTP request, so submitting a batch does not have to wait for every PDF to finish. A failed recipient does not stop the rest of the batch, and progress remains available if the browser is refreshed. Celery late acknowledgement and redelivery are enabled; leases and terminal-state checks help handle duplicate task deliveries.

### Background processing and recovery

* Beat must run alongside Celery workers. Run only one Beat scheduler.
* Queue outages leave durable jobs queued; they are published after recovery. `/ready` returns 503 when the database/schema or required Redis broker is unavailable. Acceptance itself depends on the database, not immediate queue delivery.
* Leases expire after 120 seconds and renew before each single-page render. An interrupted `processing` recipient is regenerated using the same certificate ID and storage filename.
* Only EAGAIN, EINTR, EBUSY and ETIMEDOUT filesystem errors receive up to three attempts. Permanent errors fail that recipient and processing continues.
* Recovery is at-least-once, not a claim of distributed exactly-once execution. A process stalled beyond its lease may overlap a replacement worker; filesystem writes are not fully fenced. Stop a genuinely hung worker before recovering it. Production hardening should add a heartbeat/watchdog and storage fencing.
* There is no manual retry-failed endpoint, so there is no misleading retry button. Correct invalid recipients and create a new batch. Successful records are never regenerated by ordinary task redelivery.

## Project structure

```text
backend/app/config.py        environment configuration
backend/app/db.py            engine, sessions and SQLite foreign-key settings
backend/app/models.py        jobs and recipients, keys/indexes/timestamps
backend/app/schemas.py       explicit input/output schemas
backend/app/services.py      validation, idempotent acceptance and aggregate views
backend/app/worker.py        Celery tasks, durable dispatcher, local worker
backend/app/pdf.py           actual certificate template and safe rendering
backend/app/storage.py       constrained storage-key resolution
backend/app/main.py          REST API and downloads
backend/alembic/             explicit initial migration and migration environment
backend/tests/               isolated API, PDF, worker and integration tests
frontend/src/pages/          Dashboard, Create, History, Detail
frontend/src/lib/validation.ts  CSV parser and form schemas
frontend/src/services/api.ts typed API and real download requests
frontend/src/components/ui.tsx reusable UI and accessible Radix dialog
frontend/src/test/           frontend behavior tests
scripts/smoke.py             live API -> separate worker -> PDF/ZIP verification
scripts/browser\_smoke.py     optional real browser workflow
examples/batch.json          executable two-recipient request
README.md, VERIFICATION.md, PLAN.md
```

## Run it locally

You will need three terminal windows: one for the API, one for the background worker, and one for the frontend. The Windows instructions are first because they are the easiest fit if you are using PowerShell.

### Windows PowerShell setup

**Terminal 1 — API** (from the project root):

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -r backend/requirements.txt
Set-Location backend
$env:WORKER\_MODE = "local"
$env:DATABASE\_URL = "sqlite:///./certificates.db"
$env:STORAGE\_DIR = "./storage"
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — worker** (open a new PowerShell window, then from the project root):

```powershell
.\\.venv\\Scripts\\Activate.ps1
Set-Location backend
$env:WORKER\_MODE = "local"
$env:DATABASE\_URL = "sqlite:///./certificates.db"
$env:STORAGE\_DIR = "./storage"
python -m app.worker
```

**Terminal 3 — frontend** (open a third PowerShell window, from the project root):

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. If the frontend cannot reach the API, create `frontend/.env.local` containing `VITE\_API\_URL=http://127.0.0.1:8000`, then restart the Vite dev server. API docs are at `http://127.0.0.1:8000/docs`. The virtual environment is created at the project root, so activate it from that root before changing into `backend`.

### macOS / Linux

If you are using macOS or Linux, use the commands below in three terminal windows.

Terminal 1, from project root:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend
export WORKER\_MODE=local
export DATABASE\_URL=sqlite:///./certificates.db
export STORAGE\_DIR=./storage
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2, from project root, same environment/database/storage:

```bash
. .venv/bin/activate
cd backend
export WORKER\_MODE=local
export DATABASE\_URL=sqlite:///./certificates.db
export STORAGE\_DIR=./storage
python -m app.worker
```

Terminal 3:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. API interactive OpenAPI documentation is at `http://localhost:8000/docs`; JSON schema is at `/openapi.json`. Vite serves nested routes on refresh.

The API does not automatically create tables: migrations are mandatory. The local worker uses the same processing function as Celery but polls durable database records directly, so Redis is not needed in this mode.

## Run with Docker Compose (included, but not yet verified here)

```bash
cp .env.example .env
# Edit POSTGRES\_PASSWORD and matching DATABASE\_URL for your local environment.
docker compose up --build
```

Compose starts PostgreSQL, Redis, a one-shot migration service, API, Celery worker, Beat dispatcher and built frontend served by Nginx. It waits for database health and migration completion. Host ports bind to loopback. Nginx includes SPA fallback for nested job routes.

```bash
docker compose logs -f api worker dispatcher
docker compose run --rm migrate python -m alembic check
docker compose down
```

Named volumes preserve database, broker data and certificates across `down`/`up`. **`docker compose down -v` permanently deletes those volumes.** No destructive controls are exposed in the UI.

## Use PostgreSQL and Celery for development

```bash
cp .env.example .env
# Use a URL-safe local password in .env. Percent-encode special characters in DATABASE\_URL.
docker compose up -d postgres redis
. .venv/bin/activate
set -a; . ./.env; set +a
cd backend
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In separate activated terminals, load the same root `.env`, then:

```bash
cd backend
python -m celery -A app.worker.celery worker --concurrency=2 --loglevel=info
```

```bash
cd backend
python -m celery -A app.worker.celery beat --loglevel=info --schedule=/tmp/celerybeat-schedule
```

Start frontend with `cd frontend \&\& npm ci \&\& npm run dev`. Vite reads `frontend/.env.local` if you create it; set `VITE\_API\_URL` there for a non-default API. Backend configuration uses exported environment variables; it does not silently load `.env` files.

## Environment variables

|Variable|Default / purpose|
|-|-|
|DATABASE\_URL|`sqlite:///./certificates.db`; Compose uses PostgreSQL|
|REDIS\_URL|`redis://localhost:6379/0`|
|WORKER\_MODE|`celery`; set `local` for readiness without Redis|
|STORAGE\_DIR|`./storage`; shared `/storage` volume in Compose|
|FRONTEND\_ORIGIN|`http://localhost:5173`; exact CORS allowlist|
|MAX\_BATCH|`1000`; backend maximum recipients|
|MAX\_BODY\_BYTES|`2000000`; POST body limit including chunked bodies|
|VITE\_API\_URL|`http://localhost:8000`; frontend build-time setting|
|POSTGRES\_PASSWORD|Compose requires explicit `.env` value; example is demo-only|

Frontend CSV files are limited to 1 MB and 1000 records. CSV stays in the browser; only validated JSON reaches the API. The frontend maximum is 1000; lowering backend MAX\_BATCH may reject a larger frontend batch with a structured validation error.

## Validation and error handling

* Required job fields, length bounds, printable text, valid date, nonempty batch and maximum batch size are checked server-side.
* Unexpected fields, structurally malformed recipient objects, missing keys, oversized strings and invalid job-level input reject the request with 422. Body overflow returns 413.
* Structurally valid recipient objects with empty names, invalid emails or duplicate case-insensitive email addresses are persisted as `failed / INVALID\_RECIPIENT`; valid recipients continue. The first valid occurrence of an email wins. Duplicates are scoped to one batch, not across jobs.
* Browser validation is stricter about submission: every row must be corrected first. Imported invalid rows are visible and editable; none are silently discarded.
* Rendering uses escaped text and an embedded DejaVu Sans font. Unsupported glyphs fail the affected recipient rather than producing an unreadable certificate. Complex-script shaping and full multilingual support are out of scope.
* Dates may be past or future; there is no undocumented business-date restriction.
* Reusing an Idempotency-Key with the same normalized request returns the same job; different input returns 409. The frontend retains the key for unchanged retry attempts during the current form session. Refreshing the form resets it.

## API endpoints

All job/certificate routes are under `/api/v1`. Full field schemas and status codes are available in OpenAPI.

|Method|Route|Behavior|
|-|-|-|
|GET|`/health`|Process liveness|
|GET|`/ready`|Database/schema and broker readiness|
|POST|`/api/v1/jobs`|Durable acceptance, 201; required Idempotency-Key|
|GET|`/api/v1/jobs`|`page`, `page\_size`, `search`, optional job `status`|
|GET|`/api/v1/jobs/{id}`|Job metadata and derived counts/progress|
|GET|`/api/v1/jobs/{id}/recipients`|Pagination and recipient status filter|
|GET|`/api/v1/metrics`|Actual persisted aggregate metrics|
|GET|`/api/v1/recipients/{id}/certificate`|PDF, optional `inline=true`|
|GET|`/api/v1/jobs/{id}/download`|Terminal job ZIP of successful PDFs|
|GET|`/api/v1/preview`|Real template rendered with labeled sample fields|

Unknown valid UUIDs return 404; malformed UUIDs return 422. Missing PDFs return 404. ZIP downloads before completion or with no successes return 409. Failures use JSON `detail`; request validation includes field locations and messages. Internal exceptions are not exposed.

### Example request

`examples/batch.json` contains:

```json
{
  "event": "Python Engineering",
  "organization": "Learning Lab",
  "title": "Certificate of Achievement",
  "statement": "For successfully completing the course",
  "signatory": "Course Director",
  "issue\_date": "2026-10-09",
  "recipients": \[
    {"name": "Alex Rivera", "email": "alex@example.com"},
    {"name": "Sam Taylor", "email": "sam@example.com"}
  ]
}
```

From project root:

```bash
curl -X POST http://localhost:8000/api/v1/jobs \\
  -H 'Content-Type: application/json' \\
  -H 'Idempotency-Key: technical-review-batch-1' \\
  --data-binary @examples/batch.json
```

Copy the returned `id` into JOB\_ID, then:

```bash
JOB\_ID='paste-returned-job-uuid'
curl "http://localhost:8000/api/v1/jobs/$JOB\_ID"
curl "http://localhost:8000/api/v1/jobs/$JOB\_ID/recipients?status=succeeded\&page=1\&page\_size=50"
curl "http://localhost:8000/api/v1/jobs/$JOB\_ID/download" -o certificates.zip
RECIPIENT\_ID='paste-returned-recipient-uuid'
curl "http://localhost:8000/api/v1/recipients/$RECIPIENT\_ID/certificate" -o certificate.pdf
```

### What each request does

1. `POST /api/v1/jobs` validates the batch and accepts it using the required `Idempotency-Key`.
2. `GET /api/v1/jobs/{id}` returns status, progress, counts, and timestamps.
3. `GET /api/v1/jobs/{id}/recipients` lists recipients and their processing outcomes.
4. `GET /api/v1/recipients/{id}/certificate` downloads one successful recipient's PDF.
5. `GET /api/v1/jobs/{id}/download` downloads a ZIP of successful PDFs once the job is terminal and has at least one success.

You can also exercise these flows through the frontend: create a batch manually or import a CSV, inspect the job details and recipient statuses, preview generated certificates, and download the results.

Creation response includes all job fields plus `status: queued`, `total: 2`, `pending: 2`, `processing: 0`, `succeeded: 0`, `failed: 0`, `progress: 0`. After successful processing those become `completed`, `2`, `0`, `0`, `2`, `0`, `100` respectively. Timestamps are Unix seconds, with null start/completion until available.

Recipient response is `{items: \[...], total: 2, page: 1, page\_size: 50}`. Each item includes `id`, `job\_id`, `name`, `email`, `status`, `certificate\_id`, `error\_code`, `error`, `attempts`. Storage paths are never returned.

## Tests

```bash
cd backend
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m alembic upgrade head
python -m alembic check
cd ../frontend
npm ci
npm test
npm run typecheck
npm run format:check
npm run build
```

Backend tests use an isolated temporary SQLite database with foreign keys enabled and temporary storage. They do not require network services. They generate actual PDFs and inspect text with pypdf, inspect actual ZIP contents, exercise API status/progress, force one individual failure, validate idempotency, missing files, pagination, leases and recovery. SQLite tests do not prove PostgreSQL concurrency behavior.

Frontend tests use real components, form validation and CSV parsing; HTTP is mocked at the frontend unit-test boundary. The separate live smoke test uses real HTTP and a separate worker, not a mocked backend.

With API and worker running, from project root:

```bash
python scripts/smoke.py
```

Optional browser test, with frontend also running:

```bash
python -m pip install playwright==1.57.0
python -m playwright install chromium
python scripts/browser\_smoke.py
```

I recorded the checks that were actually run, their results, and the environment limitations in [`VERIFICATION.md`](VERIFICATION.md). Browser automation could not be verified because browser downloads were blocked. Docker, PostgreSQL, and Redis were unavailable in that environment, so the Compose setup and Celery broker transport have not been tested there.

## Screenshots

**Dashboard**

View generation jobs, recipient counts, and recent batch activity.

**Create a Batch**

Configure certificate details and add recipients manually or through CSV import.

**Job History**

Review previous batches, processing status, and generation results.

**Generated Certificate**

Preview an individual PDF certificate generated by the application.



## A quick walkthrough

1. Open Dashboard; observe real empty metrics on a fresh database.
2. Open Certificate design to review the actual landscape PDF.
3. Create batch, fill course/organization fields, add two recipients or import the sample CSV. Remove the initial empty row when importing.
4. Demonstrate invalid email and duplicate-email validation, then correct the row.
5. Review batch and confirm. The job page displays durable acceptance and actual progress.
6. Filter succeeded recipients; preview and download one PDF; download ZIP.
7. Refresh the job page, then use history search to revisit the same persistent results.
8. Run backend partial-failure test to demonstrate one forced generation error does not stop another recipient.

## Storage and security notes

Files live outside frontend assets, under configurable storage. Keys and download filenames are UUID-based, never recipient-supplied paths. Temporary PDF/ZIP files are cleaned on normal exit. A hard kill may leave `.tmp` files; operators can remove old temporary files while workers are stopped. Terminal ZIPs are cached because no manual retry changes terminal results.

Back up the database and storage together. There is no automated retention policy or deletion endpoint; do not delete PDFs while their database records remain if you expect downloads to work. Local SQLite and storage persist on disk; Docker uses named volumes.

No authentication or tenant authorization is implemented. Resource checks validate that a certificate belongs to its stored recipient/job and exists, but **anyone with API access can list jobs and download certificates**. UUIDs are not an authorization mechanism. Run on localhost or an appropriately protected internal network. Production requires identity, tenant ownership checks, HTTPS, rate limiting, upload/proxy limits, monitoring, backup/retention policies and deployment hardening. CORS is not authentication.

The bundled font license is in `backend/app/assets/FONT-LICENSE.txt`. Logs avoid recipient names/emails; error responses do not expose paths or stack traces. No paid API is required.

## Current limitations and possible improvements

* PostgreSQL/Redis/Celery transport and Compose need execution on a machine with those services.
* Browser end-to-end and full visual/responsive accessibility audits remain unverified here; RTL covers labels and dialog behavior, not full WCAG compliance.
* No login, tenant isolation, certificate verification portal, email sending or manual failed-recipient retry.
* Embedded font coverage is limited; complex scripts need proper shaping and suitable fonts.
* Lease recovery assumes bounded PDF generation and responsive storage; stalled-worker fencing is not complete.
* ZIP download is disk-backed server-side but browser fetch downloads buffer a Blob; very large batches need streaming download navigation.
* Form data survives recoverable API errors, not page refresh. Idempotency keys are retained only for the current form session.
* Large-batch load testing, PostgreSQL-specific concurrency tests and automated storage retention are future hardening tasks, not claimed completed features.

