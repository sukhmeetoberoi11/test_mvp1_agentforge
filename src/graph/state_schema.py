from typing import TypedDict, Optional, List


class TicketState(TypedDict, total=False):
    ticket_id: str
    customer_id: str
    channel: str
    message_text: str
    status: str
    created_at: str
    intent: Optional[str]
    urgency: Optional[str]
    compliance_status: str
    assigned_worker: Optional[str]
    draft_response: Optional[str]
    escalation_flag: bool
    last_updated: str
    audit_log: List[dict]
    compliance_decisions: List[dict]
    agent_turns: List[dict]
    retry_count: int
    extracted_entities: dict
