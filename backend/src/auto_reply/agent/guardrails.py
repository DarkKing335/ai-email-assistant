"""
guardrails.py — Input validation & sanitization for the AutoReply layer.

All functions are pure (no I/O) and raise `GuardrailError` on violations
so the tools and workflow layers can handle them uniformly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------


class GuardrailError(ValueError):
    """Raised when an input fails a guardrail check."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Email / domain validators
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)
_DOMAIN_RE = re.compile(
    r"^@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z]{2,})+$"
)


def validate_email_address(value: str) -> str:
    """Validate and normalise a full email address.

    Returns the lowercased, stripped address or raises `GuardrailError`.
    """
    cleaned = value.strip().lower()
    if not cleaned:
        raise GuardrailError("empty_value", "Email address must not be empty.")
    if len(cleaned) > 320:
        raise GuardrailError("value_too_long", "Email address exceeds 320 characters.")
    if not _EMAIL_RE.match(cleaned):
        raise GuardrailError(
            "invalid_email", f"'{value}' is not a valid email address."
        )
    return cleaned


def validate_domain_entry(value: str) -> str:
    """Validate and normalise a domain whitelist entry (must start with @).

    Returns the lowercased, stripped value or raises `GuardrailError`.
    """
    cleaned = value.strip().lower()
    if not cleaned:
        raise GuardrailError("empty_value", "Domain entry must not be empty.")
    if len(cleaned) > 255:
        raise GuardrailError("value_too_long", "Domain entry exceeds 255 characters.")
    if not _DOMAIN_RE.match(cleaned):
        raise GuardrailError(
            "invalid_domain",
            f"'{value}' is not a valid domain entry. Use the format '@domain.com'.",
        )
    return cleaned


def validate_whitelist_value(value: str) -> tuple[str, str]:
    """Infer entry type and validate value.

    Returns ``(normalised_value, entry_type)`` where entry_type is
    ``"email"`` or ``"domain"``.
    """
    stripped = value.strip()
    if stripped.startswith("@"):
        return validate_domain_entry(stripped), "domain"
    return validate_email_address(stripped), "email"


# ---------------------------------------------------------------------------
# Sender sanitization
# ---------------------------------------------------------------------------

_ANGLE_BRACKET_RE = re.compile(r"<([^>]+)>")


def sanitize_sender(raw: str) -> tuple[str, str | None]:
    """Extract a clean email address (and optional display name) from a raw sender header.

    Handles the common formats:
      - ``alice@example.com``
      - ``Alice Smith <alice@example.com>``

    Returns ``(email, display_name)``; raises ``GuardrailError`` if no valid email found.
    """
    raw = raw.strip()
    match = _ANGLE_BRACKET_RE.search(raw)
    if match:
        email = match.group(1).strip().lower()
        display_name = raw[: match.start()].strip().strip('"').strip("'") or None
    else:
        email = raw.lower()
        display_name = None

    # Basic structural check
    if "@" not in email or "." not in email.split("@", 1)[1]:
        raise GuardrailError(
            "invalid_sender", f"Cannot extract a valid email from sender: '{raw}'"
        )

    return email, display_name


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


def is_duplicate_value(new_value: str, existing_values: list[str]) -> bool:
    """Return True if `new_value` (normalised) already exists in the list."""
    normalised = new_value.strip().lower()
    return normalised in {v.strip().lower() for v in existing_values}


# ---------------------------------------------------------------------------
# Bulk import row validation
# ---------------------------------------------------------------------------


@dataclass
class RowValidationResult:
    row_index: int
    value: str
    entry_type: str
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def validate_import_row(row_index: int, row: dict[str, Any]) -> RowValidationResult:
    """Validate a single CSV/Excel import row.

    Expected keys: ``value`` (required). Any other column — notably ``priority``
    from files exported before it was removed — is ignored rather than rejected,
    so old CSVs still import.
    """
    errors: list[str] = []
    raw_value = str(row.get("value", "")).strip()
    normalised_value = raw_value
    entry_type = "email"

    if not raw_value:
        errors.append("Missing required 'value' field.")
    else:
        try:
            normalised_value, entry_type = validate_whitelist_value(raw_value)
        except GuardrailError as exc:
            errors.append(exc.message)

    return RowValidationResult(
        row_index=row_index,
        value=normalised_value,
        entry_type=entry_type,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# LLM prompt injection guard
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(previous|above|all)\s+instructions", re.IGNORECASE),
    re.compile(r"(system|assistant)\s*prompt", re.IGNORECASE),
    re.compile(r"<\s*/?system\s*>", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
]


def check_prompt_injection(text: str, field_name: str = "input") -> None:
    """Raise GuardrailError if `text` contains obvious LLM prompt injection patterns."""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            raise GuardrailError(
                "prompt_injection_detected",
                f"The {field_name} field contains disallowed content.",
            )
