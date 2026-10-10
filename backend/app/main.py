from .logging_config import configure
import os
import tempfile
import uuid
import zipfile
from types import SimpleNamespace
from fastapi import FastAPI, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session as DBSession
from redis import Redis
from .config import ORIGIN, MAX_BODY, WORKER_MODE, REDIS_URL
from .db import session, engine
from .models import Job, Recipient
from .schemas import JobCreate, JobView, JobPage, RecipientPage, Metrics
from .services import create_job, get_job, job_view
from .storage import path_for
from .pdf import generate

configure()

app = FastAPI(title="Certify Bulk Certificate Generator", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ORIGIN],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)


@app.middleware("http")
async def limits(request: Request, call_next):
    if request.method == "POST":
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BODY:
                return JSONResponse(
                    {"detail": "Request exceeds configured size limit"}, status_code=413
                )
        request._body = bytes(body)
    return await call_next(request)


@app.exception_handler(Exception)
async def unexpected(request: Request, error: Exception):
    return JSONResponse(
        {"detail": "Service unavailable. Retry or contact the operator."}, status_code=503
    )


@app.get("/health")
def health() -> dict:
    return {"status": "alive"}


@app.get("/ready")
def ready() -> dict:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT id FROM jobs LIMIT 1"))
        if WORKER_MODE == "celery":
            Redis.from_url(REDIS_URL, socket_connect_timeout=1, socket_timeout=1).ping()
    except Exception:
        raise HTTPException(503, "Database or queue unavailable") from None
    return {"status": "ready", "worker_mode": WORKER_MODE}


@app.post("/api/v1/jobs", response_model=JobView, status_code=201)
def create(
    data: JobCreate,
    db: DBSession = Depends(session),
    idempotency_key: str = Header(min_length=1, max_length=128),
):
    return job_view(db, create_job(db, data, idempotency_key))


@app.get("/api/v1/jobs", response_model=JobPage)
def jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=300),
    status: str | None = Query(
        None, pattern="^(queued|processing|completed|completed_with_errors|failed)$"
    ),
    db: DBSession = Depends(session),
):
    filters = [Job.event.icontains(search, autoescape=True)]
    if status:
        filters.append(Job.status == status)
    total = db.scalar(select(func.count()).select_from(Job).where(*filters))
    rows = list(
        db.scalars(
            select(Job)
            .where(*filters)
            .order_by(Job.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    counts = {}
    if rows:
        for job_id, state, count in db.execute(
            select(Recipient.job_id, Recipient.status, func.count())
            .where(Recipient.job_id.in_([j.id for j in rows]))
            .group_by(Recipient.job_id, Recipient.status)
        ):
            counts.setdefault(job_id, {})[state] = count
    return {
        "items": [job_view(db, j, counts.get(j.id, {})) for j in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/api/v1/metrics", response_model=Metrics)
def metrics(db: DBSession = Depends(session)):
    counts = dict(
        db.execute(select(Recipient.status, func.count()).group_by(Recipient.status)).all()
    )
    return {
        "jobs": db.scalar(select(func.count()).select_from(Job)),
        "recipients": sum(counts.values()),
        "processed": counts.get("succeeded", 0) + counts.get("failed", 0),
        **{s: counts.get(s, 0) for s in ("succeeded", "failed", "processing", "pending")},
    }


@app.get("/api/v1/jobs/{job_id}", response_model=JobView)
def detail(job_id: uuid.UUID, db: DBSession = Depends(session)):
    return job_view(db, get_job(db, str(job_id)))


@app.get("/api/v1/jobs/{job_id}/recipients", response_model=RecipientPage)
def recipients(
    job_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: str | None = Query(None, pattern="^(pending|processing|succeeded|failed)$"),
    db: DBSession = Depends(session),
):
    get_job(db, str(job_id))
    filters = [Recipient.job_id == str(job_id)]
    if status:
        filters.append(Recipient.status == status)
    return {
        "items": list(
            db.scalars(
                select(Recipient)
                .where(*filters)
                .order_by(Recipient.position)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ),
        "total": db.scalar(select(func.count()).select_from(Recipient).where(*filters)),
        "page": page,
        "page_size": page_size,
    }


@app.get("/api/v1/recipients/{recipient_id}/certificate")
def certificate(recipient_id: uuid.UUID, inline: bool = False, db: DBSession = Depends(session)):
    recipient = db.get(Recipient, str(recipient_id))
    if not recipient or recipient.status != "succeeded" or not recipient.storage_key:
        raise HTTPException(404, "Certificate not available")
    get_job(db, recipient.job_id)
    path = path_for(recipient.storage_key)
    if not path.is_file():
        raise HTTPException(404, "Certificate file missing; contact the operator")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"certificate-{recipient.id}.pdf",
        content_disposition_type="inline" if inline else "attachment",
    )


@app.get("/api/v1/jobs/{job_id}/download")
def archive(job_id: uuid.UUID, db: DBSession = Depends(session)):
    job = get_job(db, str(job_id))
    if job.status in ("queued", "processing"):
        raise HTTPException(409, "Wait until processing completes before downloading the archive")
    rows = list(
        db.scalars(
            select(Recipient).where(Recipient.job_id == job.id, Recipient.status == "succeeded")
        )
    )
    if not rows:
        raise HTTPException(409, "No successful certificates to download")
    paths = [path_for(r.storage_key) for r in rows]
    if not all(p.is_file() for p in paths):
        raise HTTPException(404, "A certificate file is missing; contact the operator")
    target = path_for(job.id + ".zip")
    if not target.exists():
        fd, temp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        os.close(fd)
        try:
            with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as output:
                for path in paths:
                    output.write(path, path.name)
            os.replace(temp, target)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    return FileResponse(target, media_type="application/zip", filename=f"certificates-{job.id}.zip")


@app.get("/api/v1/preview")
def preview():
    with tempfile.TemporaryDirectory() as directory:
        path = __import__("pathlib").Path(directory) / "preview.pdf"
        generate(
            path,
            SimpleNamespace(
                organization="Your organization",
                title="Certificate of Achievement",
                statement="For successfully completing the learning program",
                event="Professional Development",
                issue_date="2026-10-09",
                signatory="Authorized Signatory",
            ),
            "Sample Recipient",
            "PREVIEW",
        )
        return Response(path.read_bytes(), media_type="application/pdf")
