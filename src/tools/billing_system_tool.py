import structlog
from ..settings import settings

log = structlog.get_logger()


def get_transactions(customer_id: str) -> list:
    log.info("billing_system_read", customer_id=customer_id)
    return [
        {"transaction_id": "txn_001", "amount": 49.99, "date": "2025-01-15", "status": "completed"},
        {"transaction_id": "txn_002", "amount": 49.99, "date": "2025-01-15", "status": "completed"},
    ]


def process_refund(customer_id: str, transaction_id: str, amount: float) -> dict:
    if amount > settings.billing_write_cap:
        raise ValueError(f"Refund amount ${amount} exceeds automated cap of ${settings.billing_write_cap}")
    log.info("billing_system_write", customer_id=customer_id, transaction_id=transaction_id, amount=amount)
    return {"refund_id": f"ref_{transaction_id}", "status": "processed", "amount": amount}
