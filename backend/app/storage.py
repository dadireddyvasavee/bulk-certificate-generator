import re
from pathlib import Path
from .config import STORAGE


def path_for(key: str) -> Path:
    if not re.fullmatch(r"[a-f0-9-]{36}\.(pdf|zip)", key):
        raise ValueError("Invalid storage key")
    STORAGE.mkdir(parents=True, exist_ok=True)
    return STORAGE / key
