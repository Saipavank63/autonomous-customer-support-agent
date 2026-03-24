"""Safety layer: PII detection and off-topic filtering.

Uses regex-based PII detection (credit cards, SSNs, etc.) and a keyword
classifier to reject off-topic or unsafe prompts before they reach the agent.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

import structlog

logger = structlog.get_logger()


class ViolationType(str, Enum):
    PII_DETECTED = "pii_detected"
    OFF_TOPIC = "off_topic"
    PROMPT_INJECTION = "prompt_injection"


@dataclass
class GuardrailResult:
    safe: bool
    violations: List[ViolationType]
    sanitized_text: Optional[str] = None
    details: str = ""


# PII patterns
_PII_PATTERNS = {
    "credit_card": re.compile(
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|"
        r"3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12})\b"
    ),
    "ssn": re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b"),
    "bank_account": re.compile(r"\b\d{8,17}\b"),
}

_PII_MASK = {
    "credit_card": "[REDACTED_CC]",
    "ssn": "[REDACTED_SSN]",
    "bank_account": None,  # too many false positives, flag only
}

# Off-topic signals - things a customer support bot shouldn't engage with
_OFF_TOPIC_KEYWORDS = [
    "write me a poem",
    "write me a story",
    "ignore your instructions",
    "pretend you are",
    "act as",
    "you are now",
    "tell me a joke",
    "what is the meaning of life",
    "who won the election",
    "generate code",
    "write python",
    "explain quantum",
    "recipe for",
]

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a|an)\s+", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all|your)\s+", re.IGNORECASE),
    re.compile(r"override\s+(?:safety|rules|guidelines)", re.IGNORECASE),
]


def detect_pii(text: str) -> Tuple[List[str], str]:
    """Scan text for PII patterns. Returns (found_types, sanitized_text)."""
    found = []
    sanitized = text

    for pii_type, pattern in _PII_PATTERNS.items():
        if pattern.search(text):
            found.append(pii_type)
            mask = _PII_MASK.get(pii_type)
            if mask:
                sanitized = pattern.sub(mask, sanitized)

    return found, sanitized


def detect_off_topic(text: str) -> bool:
    """Check if the message appears off-topic for customer support."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in _OFF_TOPIC_KEYWORDS)


def detect_injection(text: str) -> bool:
    """Check for prompt injection attempts."""
    return any(p.search(text) for p in _INJECTION_PATTERNS)


def run_guardrails(text: str) -> GuardrailResult:
    """Run the full safety pipeline on user input.

    Returns a GuardrailResult indicating whether the input is safe to
    pass to the agent, with any PII redacted from the sanitized text.
    """
    violations = []
    details_parts = []

    # PII check
    pii_types, sanitized = detect_pii(text)
    if pii_types:
        violations.append(ViolationType.PII_DETECTED)
        details_parts.append(
            f"PII detected ({', '.join(pii_types)}). Sensitive data has been redacted."
        )
        logger.warning("guardrail_pii_detected", types=pii_types)

    # Off-topic check
    if detect_off_topic(text):
        violations.append(ViolationType.OFF_TOPIC)
        details_parts.append(
            "Your message appears to be outside the scope of customer support. "
            "I can help with orders, refunds, account questions, and shipping."
        )
        logger.warning("guardrail_off_topic", text_preview=text[:80])

    # Injection check
    if detect_injection(text):
        violations.append(ViolationType.PROMPT_INJECTION)
        details_parts.append("Message flagged by safety filter.")
        logger.warning("guardrail_injection_attempt", text_preview=text[:80])

    is_safe = ViolationType.OFF_TOPIC not in violations and \
              ViolationType.PROMPT_INJECTION not in violations

    return GuardrailResult(
        safe=is_safe,
        violations=violations,
        sanitized_text=sanitized if pii_types else text,
        details=" | ".join(details_parts) if details_parts else "",
    )
