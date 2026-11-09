"""Journal d'audit au format JSON Lines + empreinte d'intégrité SHA-256."""
import hashlib
import json
import logging
import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from .config import settings

logger = logging.getLogger("audit")
_lock = threading.Lock()


def canonical_json(rows) -> bytes:
    """Sérialisation déterministe : clés triées, sans espaces, UTF-8.
    C'est CE flux d'octets qui est mesuré (poids) et hashé (SHA-256)."""
    return json.dumps(
        rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def write_audit(event: dict) -> dict:
    record = {"audit_id": str(uuid.uuid4()), "timestamp_utc": utc_now_iso(), **event}
    line = json.dumps(record, ensure_ascii=False, default=str)
    with _lock:
        path = Path(settings.audit_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    logger.info(line)
    return record


def read_last(n: int = 50) -> list[dict]:
    path = Path(settings.audit_log_path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        last = deque(f, maxlen=n)
    return [json.loads(x) for x in reversed(last)]  # plus récent d'abord