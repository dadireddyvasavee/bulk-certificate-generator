from alembic import context
from app.db import engine
from app.models import Job

with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Job.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
