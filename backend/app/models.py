import time
import uuid
from sqlalchemy import ForeignKey, String, Float, Integer, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def uid() -> str:
    return str(uuid.uuid4())


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    event: Mapped[str] = mapped_column(String(300))
    organization: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200))
    statement: Mapped[str] = mapped_column(String(500))
    signatory: Mapped[str] = mapped_column(String(200), default="")
    issue_date: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    started_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    lease_until: Mapped[float] = mapped_column(Float, default=0)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    fingerprint: Mapped[str] = mapped_column(String(64))


class Recipient(Base):
    __tablename__ = "recipients"
    __table_args__ = (
        UniqueConstraint("job_id", "position"),
        Index("ix_recipient_job_status", "job_id", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    certificate_id: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)
