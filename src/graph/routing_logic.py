from ..settings import settings


def route_by_intent(intent: str, urgency: str) -> str:
    if urgency == "critical":
        return "human_escalation"
    routing = {
        "billing": "billing_agent",
        "technical": "technical_agent",
        "general": "general_agent",
        "escalate": "human_escalation",
    }
    return routing.get(intent, "general_agent")


def should_escalate_after_compliance(retry_count: int) -> bool:
    return retry_count >= settings.max_compliance_retries
