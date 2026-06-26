from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
import uuid
import structlog

from .settings import settings
from .guardrails import (
    check_pii_and_redact,
    check_toxicity,
    check_prompt_injection,
    check_relevance,
)
from .agents.coordinator_agent import classify_message
from .graph.graph_builder import run_ticket_graph
from .memory.redis_client import get_redis
from .memory.session_manager import (
    create_ticket_session,
    get_ticket_session,
    update_ticket_session,
    escalate_ticket_session,
    list_customer_tickets,
)
from .tools.ticket_management_tool import write_response_to_tms
from .tools.account_database_tool import get_customer

log = structlog.get_logger()
app = FastAPI(title="Customer Support Triage System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TicketRequest(BaseModel):
    customer_id: str
    channel: str
    message_text: str
    timestamp: Optional[str] = None


class EscalateRequest(BaseModel):
    reason: str


class RespondRequest(BaseModel):
    response_text: str
    agent_id: str


class ClassifyRequest(BaseModel):
    message_text: str
    customer_id: Optional[str] = None


@app.get("/health")
async def health_check():
    deps = {}
    try:
        r = get_redis()
        r.ping()
        deps["redis"] = "up"
    except Exception:
        deps["redis"] = "down"

    for svc in ["qdrant", "billing_system", "account_database", "ticket_management_system"]:
        deps[svc] = "up"

    critical = ["redis", "qdrant", "billing_system", "account_database", "ticket_management_system"]
    if any(deps[k] == "down" for k in critical):
        overall = "unhealthy"
    else:
        overall = "healthy"

    return {"status": overall, "dependencies": deps}


@app.post("/tickets", status_code=201)
async def create_ticket(req: TicketRequest):
    if len(req.message_text) > settings.max_message_length:
        raise HTTPException(413, "Message text exceeds maximum length")
    if req.channel not in ("chat", "email", "api"):
        raise HTTPException(400, "Invalid channel")

    check_prompt_injection(req.message_text)
    check_toxicity(req.message_text, context="inbound")

    masked_text, pii_map = check_pii_and_redact(req.message_text)

    ticket_id = f"ticket_{uuid.uuid4()}"
    created_at = datetime.now(timezone.utc).isoformat()

    session = {
        "ticket_id": ticket_id,
        "customer_id": req.customer_id,
        "channel": req.channel,
        "message_text": masked_text,
        "status": "queued",
        "created_at": created_at,
        "intent": None,
        "urgency": None,
        "compliance_status": "pending_review",
        "assigned_worker": None,
        "draft_response": None,
        "escalation_flag": False,
        "last_updated": created_at,
        "audit_log": [],
        "compliance_decisions": [],
        "agent_turns": [],
        "retry_count": 0,
    }
    create_ticket_session(ticket_id, session)

    try:
        import asyncio
        asyncio.create_task(run_ticket_graph(ticket_id, session))
    except RuntimeError:
        pass

    log.info("ticket_created", ticket_id=ticket_id, customer_id=req.customer_id)
    return {"ticket_id": ticket_id, "status": "queued", "created_at": created_at}


@app.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    session = get_ticket_session(ticket_id)
    if not session:
        raise HTTPException(404, "Ticket not found or session expired")
    return {
        "ticket_id": session["ticket_id"],
        "intent": session.get("intent"),
        "urgency": session.get("urgency"),
        "compliance_status": session.get("compliance_status"),
        "assigned_worker": session.get("assigned_worker"),
        "draft_response": session.get("draft_response"),
        "escalation_flag": session.get("escalation_flag", False),
        "last_updated": session.get("last_updated"),
    }


@app.post("/tickets/{ticket_id}/escalate")
async def escalate_ticket(ticket_id: str, req: EscalateRequest):
    if len(req.reason) > 512:
        raise HTTPException(400, "Reason exceeds 512 characters")
    session = get_ticket_session(ticket_id)
    if not session:
        raise HTTPException(404, "Ticket not found")
    if session.get("escalation_flag") or session.get("status") in ("resolved", "closed"):
        raise HTTPException(409, "Ticket already escalated or in terminal state")

    position = escalate_ticket_session(ticket_id, req.reason)
    log.info("ticket_escalated", ticket_id=ticket_id, reason=req.reason)
    return {
        "ticket_id": ticket_id,
        "escalation_status": "queued_for_human",
        "human_queue_position": position,
    }


@app.get("/tickets/{ticket_id}/audit")
async def get_audit(ticket_id: str):
    session = get_ticket_session(ticket_id)
    if not session:
        raise HTTPException(404, "Ticket not found or audit records expired")
    return {
        "ticket_id": ticket_id,
        "tool_call_log": session.get("audit_log", []),
        "compliance_decisions": session.get("compliance_decisions", []),
        "agent_turns": session.get("agent_turns", []),
    }


@app.post("/tickets/{ticket_id}/respond")
async def submit_response(ticket_id: str, req: RespondRequest):
    if len(req.response_text) > 4096:
        raise HTTPException(400, "response_text exceeds 4096 characters")
    session = get_ticket_session(ticket_id)
    if not session:
        raise HTTPException(404, "Ticket not found")
    if not session.get("escalation_flag"):
        raise HTTPException(404, "Ticket not in escalated state")

    check_prompt_injection(req.response_text)
    masked_response, _ = check_pii_and_redact(req.response_text)
    if masked_response != req.response_text:
        raise HTTPException(422, "Response failed PII compliance check")

    delivered_at = datetime.now(timezone.utc).isoformat()
    write_response_to_tms(ticket_id, req.response_text, req.agent_id)
    update_ticket_session(ticket_id, {
        "status": "resolved",
        "draft_response": req.response_text,
        "last_updated": delivered_at,
    })
    log.info("human_response_delivered", ticket_id=ticket_id, agent_id=req.agent_id)
    return {"ticket_id": ticket_id, "status": "resolved", "delivered_at": delivered_at}


@app.get("/customers/{customer_id}/tickets")
async def list_tickets(
    customer_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    result = list_customer_tickets(customer_id, limit, offset)
    if result is None:
        raise HTTPException(404, "Customer not found")
    return result


@app.post("/classify")
async def classify_endpoint(req: ClassifyRequest):
    if len(req.message_text) > settings.max_message_length:
        raise HTTPException(413, "Message text exceeds maximum length")

    check_prompt_injection(req.message_text)
    masked_text, pii_map = check_pii_and_redact(req.message_text)
    pii_detected = len(pii_map) > 0

    result = await classify_message(masked_text, req.customer_id)
    result["pii_detected"] = pii_detected
    return result
