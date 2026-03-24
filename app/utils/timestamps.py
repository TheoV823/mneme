from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).isoformat()
