# Senior engineering audit and remediation

Independent audit of the Bulk Certificate Generator, performed by taking ownership of the existing implementation rather than regenerating it. The prior implementation is largely sound; this report records what was inspected, the defects found with evidence, what was fixed, and what remains unverified in this environment.

## Environment

Windows (win32), PowerShell, Python 3.11.6, project virtualenv. **Node.js, npm, Docker, PostgreSQL, and Redis are not installed on this machine.** Frontend build/test/typecheck/lint and all PostgreSQL/Celery/Redis/Docker/browser integration therefore could not be executed here and are reported as unverified, not as passing.

## Feature-to-implementation map (verified by reading + running)

| Requirement | Implementation | Evidence |
| --- | --- | --- |
| Durable job acceptance, 201, idempotency | `services.create_job`, `main.create` | `test_idempotency`, `test_complete_workflow` |
| Individual recipient validation / duplicate-email policy | `services.create_job` (per-row validate, casefold dedupe) | `test_invalid_individuals_and_duplicates` |
| Personalized PDFs, escaped + wrapped text, glyph check | `pdf.generate` | `test_complete_workflow` (pypdf text), `test_long_escaped_text`, `test_unsupported_glyph_is_isolated` |
| Atomic PDF writes, stable certificate IDs across retries | `worker.process`, `pdf.generate` (temp + `os.replace`) | `test_transient_retry`, `test_duplicate_delivery_after_completion_is_idempotent` |
| Job lease claim / renewal / recovery | `worker.process` atomic UPDATE + token | `test_active_lease_prevents_duplicate_work`, `test_stale_recovery` |
| Failure isolation + terminal status | `worker.process` state aggregation | `test_partial_failure`, `test_no_success` |
| ZIP of successes only, cached, fail-closed on missing file | `main.archive` | `test_cached_archive_rejected_when_source_file_removed` |
| Storage-key traversal protection | `storage.path_for` regex | `test_storage_traversal` |
| Metrics / pagination / filtering | `main.metrics`, `main.jobs`, `main.recipients` | `test_metrics_reflect_persisted_recipient_states`, `test_recipient_status_filter_and_counts`, `test_pagination` |
| Migrations from empty DB | `alembic/versions/0001_initial.py` | `alembic upgrade/check/downgrade/upgrade` on SQLite |

## Prioritized defect list

### Critical
None found. No data-loss, no injection, no traversal, no secret exposure defect was identified. Error responses are sanitized (`main.unexpected` returns a generic 503; worker failures store a safe code/message — confirmed by `test_partial_failure` asserting the private path string never reaches the API).

### High
None found. Core workflow (accept → process → PDF → ZIP) is verified end-to-end by the live smoke test and the backend suite.

### Medium
1. **CSV import left a blank starter row that fails validation.** `Create.tsx` initialised the form with one empty recipient row and `importText` always *appended*, so an import produced `[blank, ...imported]`. The README demo even instructed users to "remove the initial empty row when importing" — a documented workaround for a UX defect.
   - *Impact:* every CSV/paste import forced a manual delete or a confusing validation error on an empty row.
   - *Fix:* `importText` now detects when the form holds only blank rows and `replace()`s them; it still appends when real rows exist. README demo text updated. Covered by two rewritten/added frontend tests.
   - *Verification status:* logic verified by reading; frontend test run not possible here (no Node). Tests were updated to assert the new behavior.

### Low
2. **Dead/contradictory CSS rule.** `styles.css` set `.file-button input { display: none }` and then, at the end of the file, re-declared `.file-button input { display: block; max-width: 250px }`. The first rule was dead, and the visible raw file input next to the styled "Import CSV" label looked unpolished.
   - *Fix:* removed the dead rule; replaced the override with a standard visually-hidden-but-focusable pattern plus `.file-button:focus-within` outline, so the styled label is the only visible control while keyboard and screen-reader access are preserved.
   - *Verification status:* CSS reviewed; visual/browser verification not possible here.
3. **`/api/v1/preview` regenerates the PDF on every request with no cache headers.** Minor inefficiency on a demo endpoint; left as-is to avoid caching a template that can change between deployments. Documented, not changed.
4. **Global `Exception` handler returns 503 for genuine 500-class programming errors.** This correctly avoids leaking stack traces, but 503 implies "retry" for what may be deterministic. Accepted as a reasonable security-over-precision tradeoff; documented, not changed.

### Previously fixed (earlier in this engagement)
- **Undisposed SQLAlchemy engine broke test teardown on Windows** (temp DB file stayed locked, `pytest` exited non-zero despite all tests passing). Fixed with a session-scoped dispose/cleanup fixture in `conftest.py`; regression test `test_sqlite_engine_releases_file_after_dispose`.
- **Certificate template** redesigned for a professional look (navy/gold palette, double-keyline border, typographic hierarchy, signature-line footer with ellipsis-truncation guard). Verified by rendering sample + stress PDFs to images and by the PDF-text tests.

## Deliberate non-changes (working code preserved)

- The commit-then-dispatch design (durable `queued` row acted on by a Beat dispatcher every 10s) is intentional and avoids a commit/enqueue gap; left intact.
- Lease-based at-least-once processing is correctly documented as **not** exactly-once; no false guarantee added.
- No authentication was added. It is out of scope and documented as such; UUIDs and CORS are explicitly stated not to be authentication (see README security section). Adding a half-built login would reduce, not increase, quality.
- No speculative abstractions, repositories, or dependencies introduced.
