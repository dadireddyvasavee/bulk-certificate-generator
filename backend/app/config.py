import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./certificates.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
WORKER_MODE = os.getenv("WORKER_MODE", "celery")
STORAGE = Path(os.getenv("STORAGE_DIR", "./storage")).resolve()
MAX_BATCH = int(os.getenv("MAX_BATCH", "1000"))
MAX_BODY = int(os.getenv("MAX_BODY_BYTES", "2000000"))
ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
