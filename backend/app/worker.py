from .logging_config import configure
import errno
import logging
import time
from sqlalchemy import select, update
from celery import Celery
from .config import REDIS_URL
from .db import Session
from .models import Job, Recipient, uid
from .storage import path_for
from .pdf import generate

configure()
logger = logging.getLogger(__name__)
celery = Celery("certificates", broker=REDIS_URL)
celery.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    beat_schedule={"recover-durable-jobs": {"task": "app.worker.dispatch", "schedule": 10.0}},
)


@celery.task(name="app.worker.process")
def process(job_id: str) -> None:
    token = uid()
    with Session() as db:
        claimed = db.execute(
            update(Job)
            .where(
                Job.id == job_id,
                Job.status.in_(["queued", "processing"]),
                Job.lease_until < time.time(),
            )
            .values(status="processing", lease_token=token, lease_until=time.time() + 120)
        )
        db.commit()
        if not claimed.rowcount:
            return
        job = db.get(Job, job_id)
        if job.started_at is None:
            job.started_at = time.time()
            db.commit()
        ids = list(
            db.scalars(
                select(Recipient.id)
                .where(Recipient.job_id == job_id, Recipient.status.in_(["pending", "processing"]))
                .order_by(Recipient.position)
            )
        )
        for recipient_id in ids:
            # Renew the job lease before each bounded single-page render.
            renewed = db.execute(
                update(Job)
                .where(Job.id == job_id, Job.lease_token == token)
                .values(lease_until=time.time() + 120)
            )
            db.commit()
            if not renewed.rowcount:
                return
            recipient = db.get(Recipient, recipient_id)
            recipient.status = "processing"
            recipient.attempts += 1
            recipient.certificate_id = recipient.certificate_id or uid()
            recipient.storage_key = recipient.id + ".pdf"
            db.commit()
            try:
                # Retry only transient filesystem errors, at most three attempts.
                for attempt in range(3):
                    try:
                        generate(
                            path_for(recipient.storage_key),
                            job,
                            recipient.name,
                            recipient.certificate_id,
                        )
                        break
                    except OSError as error:
                        if (
                            error.errno
                            not in (errno.EAGAIN, errno.EINTR, errno.EBUSY, errno.ETIMEDOUT)
                            or attempt == 2
                        ):
                            raise
                        time.sleep(0.1 * (attempt + 1))
                recipient.status = "succeeded"
                recipient.error = recipient.error_code = None
            except Exception:
                logger.error("certificate_generation_failed", extra={"recipient_id": recipient.id})
                recipient.status = "failed"
                recipient.error_code = "GENERATION_FAILED"
                recipient.error = (
                    "Certificate generation failed. Contact the operator with this recipient ID."
                )
                recipient.storage_key = None
            recipient.updated_at = time.time()
            db.commit()
        states = list(db.scalars(select(Recipient.status).where(Recipient.job_id == job_id)))
        if any(s in ("pending", "processing") for s in states):
            return
        status = (
            "completed"
            if all(s == "succeeded" for s in states)
            else "completed_with_errors"
            if "succeeded" in states
            else "failed"
        )
        db.execute(
            update(Job)
            .where(Job.id == job_id, Job.lease_token == token)
            .values(status=status, completed_at=time.time(), lease_until=0, lease_token=None)
        )
        db.commit()


@celery.task(name="app.worker.dispatch")
def dispatch() -> None:
    with Session() as db:
        ids = list(
            db.scalars(
                select(Job.id)
                .where(Job.status.in_(["queued", "processing"]), Job.lease_until < time.time())
                .limit(100)
            )
        )
    for job_id in ids:
        process.delay(job_id)


def local_once() -> None:
    with Session() as db:
        ids = list(
            db.scalars(
                select(Job.id)
                .where(Job.status.in_(["queued", "processing"]), Job.lease_until < time.time())
                .limit(100)
            )
        )
    for job_id in ids:
        process(job_id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            local_once()
        except Exception:
            logger.error("local_worker_iteration_failed")
        time.sleep(1)
