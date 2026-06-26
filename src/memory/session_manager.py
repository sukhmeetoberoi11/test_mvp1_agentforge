import json
from datetime import datetime, timezone
from typing import Optional
from .redis_client import get_redis
from ..settings import settings

PREFIX = "ticket:"
CUSTOMER_PREFIX = "customer_tickets:"
HUMAN_QUEUE_KEY = "human_escalation_queue"


def create_ticket_session(ticket_id: str, session: dict) -> None:
    r = get_redis()
    key = f"{PREFIX}{ticket_id}"
    r.setex(key, settings.redis_active_ttl, json.dumps(session))
    customer_id = session.get("customer_id", "")
    if customer_id:
        r.lpush(f"{CUSTOMER_PREFIX}{customer_id}", ticket_id)


def get_ticket_session(ticket_id: str) -> Optional[dict]:
    r = get_redis()
    data = r.get(f"{PREFIX}{ticket_id}")
    return json.loads(data) if data else None


def update_ticket_session(ticket_id: str, updates: dict) -> Optional[dict]:
    r = get_redis()
    key = f"{PREFIX}{ticket_id}"
    data = r.get(key)
    if not data:
        return None
    session = json.loads(data)
    session.update(updates)
    session["last_updated"] = datetime.now(timezone.utc).isoformat()
    ttl = r.ttl(key)
    r.setex(key, max(ttl, 1), json.dumps(session))
    return session


def escalate_ticket_session(ticket_id: str, reason: str) -> int:
    r = get_redis()
    r.rpush(HUMAN_QUEUE_KEY, ticket_id)
    position = r.llen(HUMAN_QUEUE_KEY)
    update_ticket_session(ticket_id, {
        "escalation_flag": True,
        "status": "escalated",
        "escalation_reason": reason,
    })
    return position


def list_customer_tickets(customer_id: str, limit: int, offset: int) -> Optional[dict]:
    r = get_redis()
    ticket_ids = r.lrange(f"{CUSTOMER_PREFIX}{customer_id}", 0, -1)
    if ticket_ids is None:
        return None
    total = len(ticket_ids)
    page_ids = ticket_ids[offset: offset + limit]
    tickets = []
    for tid in page_ids:
        session = get_ticket_session(tid)
        if session:
            tickets.append({
                "ticket_id": tid,
                "intent": session.get("intent"),
                "urgency": session.get("urgency"),
                "status": session.get("status"),
                "created_at": session.get("created_at"),
            })
    return {"customer_id": customer_id, "total": total, "tickets": tickets}
