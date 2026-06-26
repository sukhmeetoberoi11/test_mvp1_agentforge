import anthropic
import structlog
from ..settings import settings
from ..tools.knowledge_base_tool import search_knowledge_base
from ..tools.account_database_tool import get_device_logs
from ..agents.coordinator_agent import SYSTEM_PROMPT

log = structlog.get_logger()


async def handle_technical_ticket(ticket_id: str, customer_id: str, message_text: str, entities: dict) -> str:
    kb_results = search_knowledge_base(message_text, limit=3)
    device_logs = get_device_logs(customer_id)

    context_parts = []
    for r in kb_results:
        context_parts.append(f"[KB] {r.get('content', '')} (score: {r.get('score', 0):.2f})")
    if device_logs:
        context_parts.append(f"[Device Logs] {device_logs}")

    context = "\n".join(context_parts) or "No additional context available."
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    prompt = f"""You are the Technical Agent. Diagnose and resolve the following technical issue.

Customer message: {message_text}
Extracted entities: {entities}
Knowledge base context:\n{context}

Provide a step-by-step resolution with citations from the knowledge base where applicable.
Never include unmasked PII in your response."""

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    draft = response.content[0].text.strip()
    log.info("technical_agent_draft", ticket_id=ticket_id)
    return draft
