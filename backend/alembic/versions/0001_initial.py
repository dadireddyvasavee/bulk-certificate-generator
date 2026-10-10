"""Initial persistent jobs and recipients schema."""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        *[
            sa.Column(n, sa.String(length), nullable=False)
            for n, length in [
                ("event", 300),
                ("organization", 200),
                ("title", 200),
                ("statement", 500),
                ("signatory", 200),
                ("issue_date", 10),
                ("status", 30),
                ("idempotency_key", 128),
                ("fingerprint", 64),
            ]
        ],
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("started_at", sa.Float()),
        sa.Column("completed_at", sa.Float()),
        sa.Column("lease_until", sa.Float(), nullable=False),
        sa.Column("lease_token", sa.String(36)),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])
    op.create_table(
        "recipients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("certificate_id", sa.String(36), unique=True),
        sa.Column("storage_key", sa.String(80)),
        sa.Column("error_code", sa.String(40)),
        sa.Column("error", sa.String(500)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=False),
        sa.UniqueConstraint("job_id", "position"),
    )
    op.create_index("ix_recipient_job_status", "recipients", ["job_id", "status"])


def downgrade():
    op.drop_table("recipients")
    op.drop_table("jobs")
