import io
import uuid
import zipfile
import pytest
from pypdf import PdfReader
from sqlalchemy import select
from app import worker
from app.db import Session
from app.models import Recipient, Job
from app.storage import path_for


def create(client, payload, key="test-key"):
    response = client.post("/api/v1/jobs", json=payload, headers={"Idempotency-Key": key})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_complete_workflow(client, payload):
    job_id = create(client, payload)
    initial = client.get(f"/api/v1/jobs/{job_id}").json()
    assert initial["pending"] == 2 and initial["progress"] == 0
    worker.process(job_id)
    result = client.get(f"/api/v1/jobs/{job_id}").json()
    assert result["status"] == "completed" and result["progress"] == 100
    assert result["started_at"] and result["completed_at"]
    rows = client.get(f"/api/v1/jobs/{job_id}/recipients").json()["items"]
    pdf = client.get(f"/api/v1/recipients/{rows[0]['id']}/certificate")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert "Alex Rivera" in PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
    archive = client.get(f"/api/v1/jobs/{job_id}/download")
    assert len(zipfile.ZipFile(io.BytesIO(archive.content)).namelist()) == 2
    assert client.get(f"/api/v1/jobs/{job_id}/download").content == archive.content
    worker.process(job_id)
    with Session() as db:
        assert all(r.attempts == 1 for r in db.scalars(select(Recipient)))
        assert db.get(Job, job_id).status == "completed"
    assert client.get("/api/v1/metrics").json()["succeeded"] == 2


def test_partial_failure(client, payload, monkeypatch):
    original = worker.generate

    def fail_one(path, job, name, certificate_id):
        if name == "Alex Rivera":
            raise ValueError("private server path")
        original(path, job, name, certificate_id)

    monkeypatch.setattr(worker, "generate", fail_one)
    job_id = create(client, payload)
    worker.process(job_id)
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "completed_with_errors" and job["succeeded"] == job["failed"] == 1
    rows = client.get(f"/api/v1/jobs/{job_id}/recipients?status=failed").json()["items"]
    assert "private" not in rows[0]["error"]
    archive = client.get(f"/api/v1/jobs/{job_id}/download")
    assert len(zipfile.ZipFile(io.BytesIO(archive.content)).namelist()) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"recipients": []},
        {"issue_date": "bad"},
        {"event": " "},
        {"unknown": 1},
        {"recipients": [{"name": "x", "email": "x@example.com"}] * 1001},
    ],
)
def test_bad_job(client, payload, change):
    payload.update(change)
    assert (
        client.post("/api/v1/jobs", json=payload, headers={"Idempotency-Key": "x"}).status_code
        == 422
    )


def test_invalid_individuals_and_duplicates(client, payload):
    payload["recipients"] += [
        {"name": "", "email": "broken"},
        {"name": "Duplicate", "email": "ALEX@example.com"},
    ]
    job_id = create(client, payload)
    worker.process(job_id)
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["failed"] == 2 and job["succeeded"] == 2


def test_idempotency(client, payload):
    job_id = create(client, payload)
    assert create(client, payload) == job_id
    payload["event"] = "Different"
    assert (
        client.post(
            "/api/v1/jobs", json=payload, headers={"Idempotency-Key": "test-key"}
        ).status_code
        == 409
    )
    assert client.get("/api/v1/jobs").json()["total"] == 1


def test_missing_files_and_ids(client, payload):
    missing = str(uuid.uuid4())
    assert client.get(f"/api/v1/jobs/{missing}").status_code == 404
    assert client.get(f"/api/v1/recipients/{missing}/certificate").status_code == 404
    job_id = create(client, payload)
    assert client.get(f"/api/v1/jobs/{job_id}/download").status_code == 409
    worker.process(job_id)
    with Session() as db:
        recipient = db.scalar(select(Recipient))
        path_for(recipient.storage_key).unlink()
        recipient_id = recipient.id
    assert client.get(f"/api/v1/recipients/{recipient_id}/certificate").status_code == 404
    assert client.get(f"/api/v1/jobs/{job_id}/download").status_code == 404


def test_no_success(client, payload):
    payload["recipients"] = [{"name": "", "email": "bad"}]
    job_id = create(client, payload)
    worker.process(job_id)
    assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "failed"
    assert client.get(f"/api/v1/jobs/{job_id}/download").status_code == 409


def test_pagination(client, payload):
    first = create(client, payload)
    create(client, payload, "second")
    assert len(client.get("/api/v1/jobs?page_size=1").json()["items"]) == 1
    assert client.get("/api/v1/jobs?search=Python&status=queued").json()["total"] == 2
    assert (
        client.get(f"/api/v1/jobs/{first}/recipients?page_size=1&page=2").json()["items"][0]["name"]
        == "Sam Taylor"
    )


def test_stale_recovery(client, payload):
    job_id = create(client, payload)
    with Session() as db:
        job = db.get(Job, job_id)
        job.status = "processing"
        job.lease_until = 0
        recipient = db.scalar(select(Recipient))
        recipient.status = "processing"
        db.commit()
    worker.local_once()
    assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "completed"


def test_storage_traversal():
    with pytest.raises(ValueError):
        path_for("../../secret.pdf")


def test_health_preview_and_body(client):
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    preview = client.get("/api/v1/preview")
    assert "Sample Recipient" in PdfReader(io.BytesIO(preview.content)).pages[0].extract_text()
    assert client.post("/api/v1/jobs", content=b"x" * 2000001).status_code == 413
    assert client.post("/api/v1/jobs", json={}).status_code == 422


def test_long_escaped_text(client, payload):
    payload["event"] = "Advanced <Engineering> & Design " * 9
    payload["recipients"][0]["name"] = "Alex & Rivera " * 14
    job_id = create(client, payload)
    worker.process(job_id)
    assert client.get(f"/api/v1/jobs/{job_id}").json()["succeeded"] == 2


def test_inline_preview(client, payload):
    job_id = create(client, payload)
    worker.process(job_id)
    row = client.get(f"/api/v1/jobs/{job_id}/recipients").json()["items"][0]
    response = client.get(f"/api/v1/recipients/{row['id']}/certificate?inline=true")
    assert response.headers["content-disposition"].startswith("inline")


def test_active_lease_prevents_duplicate_work(client, payload):
    import time

    job_id = create(client, payload)
    with Session() as db:
        job = db.get(Job, job_id)
        job.lease_until = time.time() + 120
        db.commit()
    worker.process(job_id)
    assert client.get(f"/api/v1/jobs/{job_id}").json()["pending"] == 2


def test_transient_retry(client, payload, monkeypatch):
    import errno

    original = worker.generate
    calls = 0

    def transient(path, job, name, certificate_id):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError(errno.EAGAIN, "temporary")
        original(path, job, name, certificate_id)

    monkeypatch.setattr(worker, "generate", transient)
    job_id = create(client, payload)
    worker.process(job_id)
    assert calls == 3
    assert client.get(f"/api/v1/jobs/{job_id}").json()["succeeded"] == 2


def test_unsupported_glyph_is_isolated(client, payload):
    payload["recipients"][0]["name"] = "Alex \U0001f680"
    job_id = create(client, payload)
    worker.process(job_id)
    result = client.get(f"/api/v1/jobs/{job_id}").json()
    assert result["failed"] == 1 and result["succeeded"] == 1


def test_sqlite_engine_releases_file_after_dispose(tmp_path):
    # Regression: on Windows an undisposed SQLAlchemy engine keeps the SQLite
    # file open, so temporary-directory cleanup fails with PermissionError even
    # when every test passes. Disposing the engine must release the file lock so
    # the database directory can be removed on every platform.
    import tempfile
    from sqlalchemy import create_engine, text

    directory = tempfile.TemporaryDirectory(dir=tmp_path)
    db_path = __import__("pathlib").Path(directory.name) / "release.db"
    local_engine = create_engine("sqlite:///" + str(db_path))
    with local_engine.connect() as connection:
        connection.execute(text("CREATE TABLE probe (id INTEGER PRIMARY KEY)"))
        connection.commit()
    assert db_path.is_file()
    local_engine.dispose()
    # With the engine disposed the file is no longer locked and cleanup succeeds.
    directory.cleanup()
    assert not db_path.exists()


def test_duplicate_delivery_after_completion_is_idempotent(client, payload):
    # Celery enables late acknowledgement and lost-worker redelivery, so the
    # same job id can be processed more than once. A redelivery of an already
    # completed job must not regenerate certificates, bump attempts, or change
    # any derived counts.
    job_id = create(client, payload)
    worker.process(job_id)
    first = client.get(f"/api/v1/jobs/{job_id}").json()
    assert first["status"] == "completed" and first["succeeded"] == 2
    with Session() as db:
        ids = {r.id: r.certificate_id for r in db.scalars(select(Recipient))}
    # Redeliver several times; the lease on a terminal job rejects the claim.
    for _ in range(3):
        worker.process(job_id)
    second = client.get(f"/api/v1/jobs/{job_id}").json()
    assert second == first
    with Session() as db:
        assert all(r.attempts == 1 for r in db.scalars(select(Recipient)))
        # Certificate identifiers are stable across redelivery.
        assert {r.id: r.certificate_id for r in db.scalars(select(Recipient))} == ids


def test_cached_archive_rejected_when_source_file_removed(client, payload):
    # The archive is cached on disk after the first build. If an underlying
    # certificate file is later removed, the download must fail closed with 404
    # rather than serve an archive that references a missing file.
    job_id = create(client, payload)
    worker.process(job_id)
    archive = client.get(f"/api/v1/jobs/{job_id}/download")
    assert len(zipfile.ZipFile(io.BytesIO(archive.content)).namelist()) == 2
    with Session() as db:
        recipient = db.scalar(select(Recipient).where(Recipient.status == "succeeded"))
        path_for(recipient.storage_key).unlink()
    assert client.get(f"/api/v1/jobs/{job_id}/download").status_code == 404


def test_metrics_reflect_persisted_recipient_states(client, payload):
    payload["recipients"] += [{"name": "", "email": "broken"}]
    job_id = create(client, payload)
    worker.process(job_id)
    metrics = client.get("/api/v1/metrics").json()
    assert metrics["jobs"] == 1
    assert metrics["recipients"] == 3
    assert metrics["succeeded"] == 2 and metrics["failed"] == 1
    assert metrics["processed"] == 3
    assert metrics["processing"] == 0 and metrics["pending"] == 0


def test_recipient_status_filter_and_counts(client, payload):
    payload["recipients"] += [{"name": "", "email": "broken"}]
    job_id = create(client, payload)
    worker.process(job_id)
    succeeded = client.get(f"/api/v1/jobs/{job_id}/recipients?status=succeeded").json()
    failed = client.get(f"/api/v1/jobs/{job_id}/recipients?status=failed").json()
    assert succeeded["total"] == 2 and all(r["status"] == "succeeded" for r in succeeded["items"])
    assert failed["total"] == 1 and failed["items"][0]["status"] == "failed"
    # Storage keys are never exposed through the recipient API.
    assert all("storage_key" not in item for item in succeeded["items"])


def test_malformed_uuid_is_422_not_503(client):
    # Path parameters are typed as UUID, so a malformed id is a validation
    # error (422), never a masked 503 from the catch-all handler.
    assert client.get("/api/v1/jobs/not-a-uuid").status_code == 422
    assert client.get("/api/v1/recipients/not-a-uuid/certificate").status_code == 422
