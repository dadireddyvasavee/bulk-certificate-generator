import hashlib
import json
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from .models import Job, Recipient
from .schemas import JobCreate, ValidRecipient


def job_view(db, job: Job, counts: dict | None = None) -> dict:
    counts = (
        counts
        if counts is not None
        else dict(
            db.execute(
                select(Recipient.status, func.count())
                .where(Recipient.job_id == job.id)
                .group_by(Recipient.status)
            ).all()
        )
    )
    total = sum(counts.values())
    result = {
        key: getattr(job, key)
        for key in (
            "id",
            "event",
            "organization",
            "title",
            "statement",
            "signatory",
            "issue_date",
            "status",
            "created_at",
            "started_at",
            "completed_at",
        )
    }
    result.update(
        {state: counts.get(state, 0) for state in ("pending", "processing", "succeeded", "failed")}
    )
    result.update(
        total=total,
        progress=round(100 * (result["succeeded"] + result["failed"]) / total, 1) if total else 0,
    )
    return result


def get_job(db, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


def create_job(db, data: JobCreate, key: str) -> Job:
    payload = data.model_dump(mode="json")
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    existing = db.scalar(select(Job).where(Job.idempotency_key == key))
    if existing:
        if existing.fingerprint != fingerprint:
            raise HTTPException(409, "Idempotency key already used for different input")
        return existing
    job = Job(
        **{k: v for k, v in payload.items() if k != "recipients"},
        idempotency_key=key,
        fingerprint=fingerprint,
    )
    db.add(job)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Job).where(Job.idempotency_key == key))
        if not existing or existing.fingerprint != fingerprint:
            raise HTTPException(409, "Conflicting submission") from None
        return existing
    seen: set[str] = set()
    for position, raw in enumerate(data.recipients):
        record = Recipient(
            job_id=job.id,
            position=position,
            name=raw.name.strip(),
            email=raw.email.strip(),
            status="pending",
        )
        try:
            valid = ValidRecipient.model_validate(raw.model_dump())
            email = str(valid.email).casefold()
            if email in seen:
                raise ValueError("Duplicate email in this batch")
            seen.add(email)
            record.name, record.email = valid.name, email
        except (ValidationError, ValueError):
            record.status = "failed"
            record.error_code = "INVALID_RECIPIENT"
            record.error = (
                "Correct the name/email or remove a duplicate email, then submit a new batch."
            )
        db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Job).where(Job.idempotency_key == key))
        if not existing or existing.fingerprint != fingerprint:
            raise HTTPException(409, "Conflicting submission") from None
        return existing
    return job
