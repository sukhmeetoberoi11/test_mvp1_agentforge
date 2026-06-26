import uuid
import structlog
from datetime import datetime, timezone

from .routing_logic import route_by_intent, should_escalate_after_compliance
from .checkpointer import save_checkpoint
from ..agents.coordinator_agent import classify_message
from ..agents.billing_agent import handle_billing_ticket
from ..agents.technical_agent import handle_technical_ticket
from ..agents.general_agent import handle_general_ticket
from ..agents.compliance_reviewer import review_draft
from ..agents.response_emitter import emit_response
from ..memory.session_manager import update_ticket_session, escalate_ticket_session
from ..guardrails import check_toxicity, check_pii_and_redact

log = structlog.get_logger()


async def run_ticket_graph(ticket_id: str, session: dict) -> None:
    try:
        update_ticket_session(ticket_id, {"status": "processing"})

        classification = await classify_message(
            session["message_text"], session.get("customer_id")
        )
        intent = classification["intent"]
        urgency = classification["urgency"]
        entities = classification.get("extracted_entities", {})

        update_ticket_session(ticket_id, {
            "intent": intent,
            "urgency": urgency,
            "extracted_entities": entities,
        })

        worker = route_by_intent(intent, urgency)
        update_ticket_session(ticket_id, {"assigned_worker": worker})

        if worker == "human_escalation":
            escalate_ticket_session(ticket_id, f"Auto-escalated: urgency={urgency}, intent={intent}")
            return

        retry_count = 0
        draft = None

        while retry_count <= 2:
            if worker == "billing_agent":
                draft = await handle_billing_ticket(
                    ticket_id, session["customer_id"], session["message_text"], session
                )
            elif worker == "technical_agent":
                draft = await handle_technical_ticket(
                    ticket_id, session["customer_id"], session["message_text"], entities
                )
            else:
                draft = await handle_general_ticket(ticket_id, session["message_text"])

            draft = check_toxicity(draft, context="outbound")
            masked_draft, _ = check_pii_and_redact(draft)

            turn_id = str(uuid.uuid4())
            turn = {
                "turn_id": turn_id,
                "assigned_worker": worker,
                "draft_response": masked_draft,
                "retrieved_context": [],
                "retry_count": retry_count,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            review = review_draft(masked_draft, session["message_text"], intent)
            review["turn_id"] = turn_id

            current = update_ticket_session(ticket_id, {
                "draft_response": masked_draft,
                "compliance_status": review["compliance_status"],
            })

            session_data = {
                "agent_turns": session.get("agent_turns", []) + [turn],
                "compliance_decisions": session.get("compliance_decisions", []) + [review],
            }
            update_ticket_session(ticket_id, session_data)
            session.update(session_data)

            if review["compliance_status"] == "approved":
                emit_response(ticket_id, masked_draft, session)
                save_checkpoint(ticket_id, session)
                return

            retry_count += 1
            log.warning("compliance_rejected", ticket_id=ticket_id, retry=retry_count,
                        reason=review.get("rejection_reason"))

            if should_escalate_after_compliance(retry_count):
                escalate_ticket_session(
                    ticket_id,
                    f"Compliance rejection limit exceeded: {review.get('rejection_reason')}"
                )
                return

    except Exception as exc:
        log.error("graph_error", ticket_id=ticket_id, error=str(exc))
        update_ticket_session(ticket_id, {"status": "escalated", "escalation_flag": True})
