import uuid
from datetime import datetime, timezone
import structlog
from ..guardrails import check_pii_and_redact, check_relevance

log = structlog.get_logger()

PROHIBITED_PHRASES = [
    "guaranteed", "we promise", "100% refund", "legal action",
    "sue", "lawsuit", "unauthorized",
]


def review_draft(draft_response: str, original_message: str, intent: str) -> dict:
    review_id = str(uuid.uuid4())
    reviewed_at = datetime.now(timezone.utc).isoformat()

    masked, pii_found = check_pii_and_redact(draft_response)
    pii_clean = len(pii_found) == 0

    prohibited_hit = next(
        (p for p in PROHIBITED_PHRASES if p.lower() in draft_response.lower()), None
    )
    policy_aligned = prohibited_hit is None

    relevant = check_relevance(draft_response, original_message, intent)

    if not pii_clean:
        return {
            "review_id": review_id,
            "compliance_status": "rejected",
            "pii_clean": False,
            "policy_aligned": policy_aligned,
            "rejection_reason": f"Unmasked PII detected: {list(pii_found.keys())}",
            "reviewed_at": reviewed_at,
            "masked_draft": masked,
        }

    if not policy_aligned:
        return {
            "review_id": review_id,
            "compliance_status": "rejected",
            "pii_clean": True,
            "policy_aligned": False,
            "rejection_reason": f"Prohibited phrase detected: '{prohibited_hit}'",
            "reviewed_at": reviewed_at,
            "masked_draft": draft_response,
        }

    if not relevant:
        return {
            "review_id": review_id,
            "compliance_status": "rejected",
            "pii_clean": True,
            "policy_aligned": True,
            "rejection_reason": "Response does not adequately address the customer's issue",
            "reviewed_at": reviewed_at,
            "masked_draft": draft_response,
        }

    log.info("compliance_approved", review_id=review_id)
    return {
        "review_id": review_id,
        "compliance_status": "approved",
        "pii_clean": True,
        "policy_aligned": True,
        "rejection_reason": None,
        "reviewed_at": reviewed_at,
        "masked_draft": draft_response,
    }
