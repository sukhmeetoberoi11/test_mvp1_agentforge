from pydantic_settings import BaseSettings
from pathlib import Path
import json


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    redis_url: str = "redis://localhost:6379"
    qdrant_url: str = "http://localhost:6333"
    max_requests_per_minute: int = 60
    max_message_length: int = 8192
    redis_active_ttl: int = 86400
    redis_resolved_ttl: int = 604800
    audit_retention_days: int = 90
    max_compliance_retries: int = 2
    billing_write_cap: float = 500.0
    relevance_threshold: float = 0.6
    toxicity_threshold: float = 0.75

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

_guardrails_path = Path(__file__).resolve().parent.parent / "config" / "guardrails.json"


def load_guardrails_config() -> dict:
    if _guardrails_path.exists():
        with open(_guardrails_path) as f:
            items = json.load(f)
        return {item["type"]: item for item in items}
    return {}


guardrails_config = load_guardrails_config()
