"""
Input sanitization and prompt injection detection.

First line of defence: catches malicious inputs before they reach
the LLM or any downstream processing.
"""

import re
from dataclasses import dataclass


@dataclass
class SanitizationResult:
    """Result of input sanitization check."""
    is_safe: bool
    sanitized_text: str
    reason: str


# ─── Prompt Injection Patterns ──────────────────────────────────
# These patterns detect common prompt injection techniques
_INJECTION_PATTERNS: list[tuple[str, str]] = [
    # Direct instruction override
    (
        r"(?i)(ignore|forget|disregard)\s+(all\s+)?(previous|prior|above|earlier)\s+"
        r"(instructions?|prompts?|rules?|context)",
        "Prompt injection: instruction override attempt",
    ),
    # System prompt extraction
    (
        r"(?i)(show|reveal|display|print|output|repeat|echo)\s+"
        r"(your|the|system)?\s*(system\s*)?(prompt|instructions?|rules?|context)",
        "Prompt injection: system prompt extraction attempt",
    ),
    # Role reassignment
    (
        r"(?i)(you\s+are\s+now|act\s+as|pretend\s+(to\s+be|you\s+are)|"
        r"from\s+now\s+on\s+you)",
        "Prompt injection: role reassignment attempt",
    ),
    # Direct SQL injection in natural language
    (
        r"(?i)(;\s*(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|EXEC|GRANT|REVOKE)\s)",
        "SQL injection: dangerous SQL statement in input",
    ),
    # Encoded injection attempts
    (
        r"(?i)(\\x[0-9a-f]{2}|\\u[0-9a-f]{4}|%[0-9a-f]{2}){3,}",
        "Encoded injection attempt detected",
    ),
    # Markdown/code fence abuse
    (
        r"```(system|assistant|admin)",
        "Prompt injection: role impersonation via code fence",
    ),
]

# ─── Dangerous SQL Keywords in Free Text ────────────────────────
_DANGEROUS_SQL_KEYWORDS = [
    "DROP TABLE", "DROP DATABASE", "DELETE FROM", "TRUNCATE TABLE",
    "INSERT INTO", "UPDATE SET", "ALTER TABLE", "CREATE TABLE",
    "EXEC ", "EXECUTE ", "GRANT ", "REVOKE ", "xp_cmdshell",
    "UNION SELECT", "OR 1=1", "' OR '1'='1",
    "WAITFOR DELAY", "BENCHMARK(", "SLEEP(",
]


def sanitize_input(user_input: str) -> SanitizationResult:
    """
    Validate and sanitize user input.

    Performs:
    1. Length validation
    2. Control character removal
    3. Prompt injection pattern detection
    4. Dangerous SQL keyword detection

    Args:
        user_input: Raw user input string.

    Returns:
        SanitizationResult with safety status and cleaned text.
    """
    # 1. Empty input
    if not user_input or not user_input.strip():
        return SanitizationResult(
            is_safe=False,
            sanitized_text="",
            reason="Empty input",
        )

    # 2. Length limit (prevent token flooding)
    if len(user_input) > 2000:
        return SanitizationResult(
            is_safe=False,
            sanitized_text=user_input[:2000],
            reason="Input exceeds maximum length of 2000 characters",
        )

    # 3. Strip control characters (keep newlines and tabs)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", user_input)
    cleaned = cleaned.strip()

    # 4. Check prompt injection patterns
    for pattern, reason in _INJECTION_PATTERNS:
        if re.search(pattern, cleaned):
            return SanitizationResult(
                is_safe=False,
                sanitized_text=cleaned,
                reason=reason,
            )

    # 5. Check dangerous SQL keywords
    upper_input = cleaned.upper()
    for keyword in _DANGEROUS_SQL_KEYWORDS:
        if keyword.upper() in upper_input:
            return SanitizationResult(
                is_safe=False,
                sanitized_text=cleaned,
                reason=f"Dangerous SQL keyword detected: {keyword}",
            )

    return SanitizationResult(
        is_safe=True,
        sanitized_text=cleaned,
        reason="Input is safe",
    )
