import hashlib
import json


def canonical_hash(data):
    """SHA-256 of canonical JSON (sorted keys, compact separators)."""
    if isinstance(data, str):
        data = json.loads(data)
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
