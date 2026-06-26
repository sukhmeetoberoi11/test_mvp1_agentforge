import json
from ..memory.redis_client import get_redis
from ..settings import settings


def save_checkpoint(ticket_id: str, state: dict) -> None:
    r = get_redis()
    key = f"checkpoint:{ticket_id}"
    r.setex(key, settings.redis_active_ttl, json.dumps(state))


def load_checkpoint(ticket_id: str) -> dict:
    r = get_redis()
    key = f"checkpoint:{ticket_id}"
    data = r.get(key)
    return json.loads(data) if data else {}
