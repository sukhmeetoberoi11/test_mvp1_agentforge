import re
import structlog
from fastapi import HTTPException
from typing import Tuple

log = structlog.get_logger()

PII_PATTERNS = [
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("PHONE", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("DATE_OF_BIRTH", re.compile(r"\b(?:dob|date of birth)[:\s]+\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b", re.IGNORECASE)),
]

TOXIC_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bkill\s+you\b", r"\bdie\b", r"\bstupid\b", r"\bidiot\b",
        r"\bmoron\b", r"\bfuck\b", r"\bshit\b", r"\bhateful\b",
        r"\bharassment\b", r"\bdiscriminate\b",
    ]
]

INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"ignore previous instructions",
        r"system\s*prompt",
        r"jailbreak",
        r"\{\{",
        r"\}\}",
        r"system:",
        r"override\s+instructions",
        r"disregard\s+(all|previous|prior)",
        r"you are now",
        r"act as if",
    ]
]


def check_pii_and_redact(text: str) -> Tuple[str, dict]:
    """Scan text for PII, replace with typed tokens, return (masked_text, pii_map)."""
    pii_map = {}
    counters: dict = {}
    result = text
    for pii_type, pattern in PII_PATTERNS:
        matches = list(pattern.finditer(result))
        for match in reversed(matches):
            counters[pii_type] = counters.get(pii_type, 0) + 1
            token = f"[{pii_type}_{counters[pii_type]}]"
            pii_map[token] = match.group()
            result = result[:match.start()] + token + result[match.end():]
    return result, pii_map


def check_toxicity(text: str, context: str = "inbound") -> str:
    """Check text for toxic content. Raises HTTPException(400) on inbound; returns filtered text for outbound."""
    for pattern in TOXIC_PATTERNS:
        if pattern.search(text):
            log.warning("toxicity_detected", context=context, pattern=pattern.pattern)
            if context == "inbound":
                raise HTTPException(400, "Message contains prohibited content")
            return pattern.sub("[filtered]", text)
    return text


def check_prompt_injection(text: str) -> None:
    """Scan for prompt injection patterns; raise HTTPException(400) if found."""
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            log.critical("prompt_injection_detected", pattern=pattern.pattern)
            raise HTTPException(400, "prompt injection detected")


def check_relevance(response_text: str, query_text: str, intent: str) -> bool:
    """Verify response relevance by checking intent keywords appear in response."""
    intent_keywords = {
        "billing": ["charge", "invoice", "refund", "subscription", "payment", "billing", "account"],
        "technical": ["error", "issue", "fix", "resolve", "technical", "problem", "crash", "update"],
        "general": ["policy", "information", "help", "faq", "question", "support"],
        "escalate": ["escalat", "human", "agent", "manager", "supervisor"],
    }
    keywords = intent_keywords.get(intent, [])
    response_lower = response_text.lower()
    query_lower = query_text.lower()
    query_words = set(query_lower.split())
    response_words = set(response_lower.split())
    overlap = query_words & response_words
    keyword_hit = any(kw in response_lower for kw in keywords)
    return keyword_hit or len(overlap) >= 3
