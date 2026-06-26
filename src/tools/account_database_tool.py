import structlog

log = structlog.get_logger()


def get_account_info(customer_id: str) -> dict:
    log.info("account_db_read", customer_id=customer_id, action="get_account_info")
    return {
        "customer_id": customer_id,
        "account_status": "active",
        "subscription_plan": "premium_monthly",
        "email": "[EMAIL_MASKED]",
    }


def get_device_logs(customer_id: str) -> list:
    log.info("account_db_read", customer_id=customer_id, action="get_device_logs")
    return [{"event": "login", "platform": "web", "timestamp": "2025-01-15T10:00:00Z"}]


def get_customer(customer_id: str) -> dict:
    log.info("account_db_read", customer_id=customer_id, action="get_customer")
    return {"customer_id": customer_id, "exists": True}
