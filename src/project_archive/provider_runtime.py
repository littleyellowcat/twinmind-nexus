"""Provider runtime guards and sanitized failure payloads."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]+"),
    re.compile(r"(?i)(api[_-]?key\s*[=:]?\s*)[A-Za-z0-9._-]+"),
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._-]+"),
]


def sanitize_provider_error(error: BaseException | str) -> str:
    """Remove likely credentials from provider error text."""

    message = str(error)
    for pattern in _SECRET_PATTERNS:
        message = pattern.sub(lambda match: f"{match.group(1)}<redacted>" if match.lastindex else "<redacted>", message)
    return message


def provider_failure_payload(
    *,
    provider: str,
    model: str | None = None,
    error: BaseException | str,
    fallback: str = "rules",
    operation: str = "live_model_call",
) -> dict[str, Any]:
    """Return a trace-safe provider failure event payload."""

    sanitized = sanitize_provider_error(error)
    category = categorize_provider_error(sanitized)
    return {
        "type": "provider.failure",
        "created_at": datetime.now(UTC).isoformat(),
        "provider": provider,
        "model": model,
        "operation": operation,
        "category": category,
        "error": sanitized,
        "fallback": fallback,
        "retryable": category in {"provider_timeout", "rate_limited", "network_unreachable"},
    }


def categorize_provider_error(message: str) -> str:
    normalized = message.lower()
    if "timeout" in normalized or "timed out" in normalized:
        return "provider_timeout"
    if "rate limit" in normalized or "429" in normalized:
        return "rate_limited"
    if "network" in normalized or "connection" in normalized or "dns" in normalized:
        return "network_unreachable"
    if "401" in normalized or "unauthorized" in normalized or "credential" in normalized:
        return "missing_credentials"
    return "provider_error"
