import structlog
from datetime import datetime, timezone
from ..tools.ticket_management_tool import write_response_to_tms
from ..memory.session_manager import update_ticket_session
from ..memory.conversation_history import append_turn

log = structlog.get_logger()


def emit_response(ticket_id: str, approved_response: str, session: dict) -> dict:
    delivered_at = datetime.now(timezone.utc).isoformat()
    write_response_to_tms(ticket_id, approved_response, agent_id="system")

    update_ticket_session(ticket_id, {
        "status": "resolved",
        "draft_response": approved_response,
        "compliance_status": "approved",
        "last_updated": delivered_at,
    })

    append_turn(ticket_id, {
        "role": "assistant",
        "content": approved_response,
        "timestamp": delivered_at,
    })

    log.info("response_emitted", ticket_id=ticket_id, delivered_at=delivered_at)
    return {"ticket_id": ticket_id, "status": "resolved", "delivered_at": delivered_at}
