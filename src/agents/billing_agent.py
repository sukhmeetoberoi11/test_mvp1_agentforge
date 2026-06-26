import anthropic
import structlog
from ..settings import settings
from ..tools.billing_system_tool import get_transactions, process_refund
from ..tools.account_database_tool import get_account_info
from ..agents.coordinator_agent import SYSTEM_PROMPT

log = structlog.get_logger()


async def handle_billing_ticket(ticket_id: str, customer_id: str, message_text: str, session: dict) -> str:
    account = get_account_info(customer_id)
    transactions = get_transactions(customer_id)

    context = f"Account info: {account}\nRecent transactions: {transactions}"
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    prompt = f"""You are the Billing Agent. Resolve the following billing issue.

Customer message: {message_text}
Account context: {context}

Rules:
- Maximum automated refund: ${settings.billing_write_cap}
- Amounts above ${settings.billing_write_cap} require human approval
- Never include unmasked PII in your response
- Be specific about actions taken

Provide a complete, helpful response to the customer."""

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    draft = response.content[0].text.strip()
    log.info("billing_agent_draft", ticket_id=ticket_id)
    return draft
