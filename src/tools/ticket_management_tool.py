import structlog
from datetime import datetime, timezone

log = structlog.get_logger()


def write_response_to_tms(ticket_id: str, response_text: str, agent_id: str) -> dict:
    delivered_at = datetime.now(timezone.utc).isoformat()
    log.info("tms_write", ticket_id=ticket_id, agent_id=agent_id, delivered_at=delivered_at)
    return {"ticket_id": ticket_id, "status": "delivered", "delivered_at": delivered_at}


def get_ticket_from_tms(ticket_id: str) -> dict:
    log.info("tms_read", ticket_id=ticket_id)
    return {"ticket_id": ticket_id, "status": "open"}
