"""
audit_pairing.py — Resolution and completion of Audit setup references (M1.3b).

A setup reference created by the Architecture Audit service is opaque,
scoped to one audit/project, and expiring. This client resolves it to
baseline provenance and reports setup completion back, so a setup initiated
from an Audit is attributable to that audit/project (G3, G7).

Failure semantics are fail-closed: any network or HTTP failure raises
:class:`PairingError` and the setup flow aborts before any local mutation.
Reference resolution is REQUIRED when ``--audit-ref`` is supplied: an
unverifiable reference is never recorded silently.

The base URL defaults to the production Architecture Audit API and can be
overridden with ``MNEME_AUDIT_API_URL``. Uses only the standard library.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

DEFAULT_AUDIT_API_URL = (
    "https://mneme-audit-api-842519822929.us-central1.run.app"
)
DEFAULT_TIMEOUT_SECONDS = 15.0

RESOLVE_PATH = "/api/v1/setup-references/{reference}"
COMPLETE_PATH = "/api/v1/setup-references/{reference}/complete"


class PairingError(Exception):
    """A pairing request failed (network, HTTP, or unparseable response)."""

    def __init__(self, message: str, status: int | None = None):
        self.status = status
        super().__init__(message)


@dataclass
class AuditPairingClient:
    """HTTP client for Audit setup-reference resolve/complete (M1.3b)."""

    base_url: str = ""
    timeout: float = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if not self.base_url:
            self.base_url = os.environ.get(
                "MNEME_AUDIT_API_URL", DEFAULT_AUDIT_API_URL
            ).rstrip("/")

    def resolve(self, reference: str) -> dict:
        """Resolve a reference to baseline provenance (non-consuming)."""
        path = RESOLVE_PATH.format(reference=urllib.parse.quote(reference, safe=""))
        return self._request("GET", path)

    def complete(
        self,
        reference: str,
        repository: str | None,
        mneme_version: str,
    ) -> dict:
        """Report setup completion (idempotent server-side)."""
        path = COMPLETE_PATH.format(reference=urllib.parse.quote(reference, safe=""))
        payload = {
            "repository": repository,
            "mneme_version": mneme_version,
        }
        return self._request("POST", path, body=payload)

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Accept": "application/json",
                **({"Content-Type": "application/json"} if data else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                status = getattr(response, "status", 200)
        except urllib.error.HTTPError as exc:
            detail = self._error_detail(exc)
            raise PairingError(
                detail or f"HTTP {exc.code} from Audit service", status=exc.code
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise PairingError(
                f"could not reach the Architecture Audit service at "
                f"{self.base_url}: {exc}"
            ) from exc
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PairingError(
                f"Audit service returned a non-JSON response (HTTP {status})"
            ) from exc
        if not isinstance(payload, dict):
            raise PairingError(
                f"Audit service returned an unexpected payload (HTTP {status})"
            )
        return payload

    @staticmethod
    def _error_detail(exc: urllib.error.HTTPError) -> str:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            return ""
        error = payload.get("error") if isinstance(payload, dict) else None
        return str(error) if error else ""


def detect_origin_remote(project_root) -> str | None:
    """Best-effort ``git remote get-url origin`` for the mismatch check."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    remote = (result.stdout or "").strip()
    return remote or None
