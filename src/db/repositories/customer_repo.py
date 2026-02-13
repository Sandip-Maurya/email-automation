"""Customer repository: query Customer by DEA or name, return trigger-shaped dict."""

from typing import Any

from sqlalchemy import select

from src.db import get_session
from src.db.models.master import Customer
from src.models.inputs import ProductAccessInput


def _parse_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes")
    return False


def fetch(inputs: ProductAccessInput) -> dict[str, Any]:
    """Find customer by dea_number (exact) or name (contains); return class_of_trade, rems_certified, etc. No match: defaults."""
    with get_session() as session:
        dea = (inputs.dea_number or "").strip()
        customer_name = (inputs.customer or "").strip().lower()
        q = select(Customer).where(Customer.is_active == True)
        if dea:
            q = q.where(Customer.dea_number == dea)
        elif customer_name:
            q = q.where(Customer.name.ilike(f"%{customer_name}%"))
        else:
            # No lookup criteria -> return defaults
            return {
                "class_of_trade": "Unknown",
                "rems_certified": False,
                "is_340b": inputs.is_340b if inputs.is_340b is not None else False,
                "address": None,
                "customer_id": None,
                "source": "db",
            }
        row = session.scalars(q).first()
        if row is None:
            return {
                "class_of_trade": "Unknown",
                "rems_certified": False,
                "is_340b": inputs.is_340b if inputs.is_340b is not None else False,
                "address": None,
                "customer_id": None,
                "source": "db",
            }
        return {
            "class_of_trade": row.class_of_trade or "Unknown",
            "rems_certified": row.rems_certified,
            "is_340b": row.is_340b,
            "address": row.address,
            "customer_id": row.customer_id,
            "source": "db",
        }
