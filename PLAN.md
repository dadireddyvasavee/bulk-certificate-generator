# Implementation checklist and architecture
- Database: SQLAlchemy Job/Recipient, Alembic migration, PostgreSQL primary, SQLite local fallback.
- Validation: strict job fields; invalid individual records persist as failed; duplicate email policy.
- PDFs: landscape ReportLab, escaped wrapped text, UUID storage, atomic replacement.
- Processing: durable queued rows act as an outbox; dispatcher republishes unfinished jobs; atomic job lease prevents concurrent work; persisted recipient boundaries.
- API: versioned creation, history, metrics, progress, recipient pagination, PDF/ZIP and preview.
- UI: dashboard, guided batch form, CSV/paste, history, detail filters and preview.
- Verification: isolated API/worker tests, frontend tests/build, migrations, live HTTP smoke.
