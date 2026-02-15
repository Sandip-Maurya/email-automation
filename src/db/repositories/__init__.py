"""DB repositories: sync functions that return trigger-shaped dicts."""

from src.db.repositories.allocation_repo import fetch as allocation_fetch
from src.db.repositories.customer_repo import fetch as customer_fetch
from src.db.repositories.email_outcome_repo import (
    get_by_message_id as email_outcome_get_by_message_id,
    has_recent_draft as email_outcome_has_recent_draft,
    insert_draft as email_outcome_insert_draft,
    supersede_by_conversation as email_outcome_supersede_by_conversation,
    update_sent as email_outcome_update_sent,
)
from src.db.repositories.inventory_repo import fetch as inventory_fetch

__all__ = [
    "inventory_fetch",
    "customer_fetch",
    "allocation_fetch",
    "email_outcome_insert_draft",
    "email_outcome_has_recent_draft",
    "email_outcome_supersede_by_conversation",
    "email_outcome_get_by_message_id",
    "email_outcome_update_sent",
]
