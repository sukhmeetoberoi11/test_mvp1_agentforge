import json
from .redis_client import get_redis
from ..settings import settings


def append_turn(ticket_id: str, turn: dict) -> None:
    r = get_redis()
    key = f"history:{ticket_id}"
    r.rpush(key, json.dumps(turn))
    r.expire(key, settings.redis_resolved_ttl)


def get_history(ticket_id: str) -> list:
    r = get_redis()
    items = r.lrange(f"history:{ticket_id}", 0, -1)
    return [json.loads(i) for i in items]
