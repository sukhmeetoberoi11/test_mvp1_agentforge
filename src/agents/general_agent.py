import anthropic
import structlog
from ..settings import settings
from ..tools.knowledge_base_tool import search_knowledge_base
from ..agents.coordinator_agent import SYSTEM_PROMPT

log = structlog.get_logger()


async def handle_general_ticket(ticket_id: str, message_text: str) -> str:
    kb_results = search_knowledge_base(message_text, limit=3)
    context = "\n".join(r.get("content", "") for r in kb_results) or "No relevant articles found."

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = f"""You are the General Support Agent. Answer the following customer question using the knowledge base.

Customer message: {message_text}
Knowledge base context:\n{context}

If the question is out of scope or requires specialist handling, indicate that escalation is needed.
Never include unmasked PII in your response."""

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    draft = response.content[0].text.strip()
    log.info("general_agent_draft", ticket_id=ticket_id)
    return draft
