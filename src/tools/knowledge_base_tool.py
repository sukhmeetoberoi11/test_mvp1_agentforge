import structlog

log = structlog.get_logger()


def search_knowledge_base(query: str, limit: int = 3) -> list:
    log.info("kb_query", query_preview=query[:80], limit=limit)
    return [
        {
            "content": "Refunds under $500 may be processed automatically by billing agents without human approval.",
            "source": "policy_documents",
            "score": 0.85,
        },
        {
            "content": "For upload timeout errors, check network connectivity and file size limits (max 100MB).",
            "source": "knowledge_base_articles",
            "score": 0.78,
        },
    ]
