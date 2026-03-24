import structlog
from langchain_core.tools import tool
from sqlalchemy import select

from src.db.connection import get_session
from src.db.models import Customer

logger = structlog.get_logger()


@tool
async def update_customer_info(
    email: str,
    name: str = "",
    phone: str = "",
    notes: str = "",
) -> str:
    """Update a customer's CRM record by email. Only the fields provided with
    non-empty values will be updated.

    Args:
        email: Customer email to look up (required).
        name: New name (leave empty to keep current).
        phone: New phone number (leave empty to keep current).
        notes: Additional notes to append to the customer record.
    """
    async with get_session() as session:
        result = await session.execute(
            select(Customer).where(Customer.email == email)
        )
        customer = result.scalar_one_or_none()

        if not customer:
            return f"No customer found with email '{email}'."

        updates = []

        if name:
            customer.name = name
            updates.append(f"name -> '{name}'")

        if phone:
            customer.phone = phone
            updates.append(f"phone -> '{phone}'")

        if notes:
            separator = "\n" if customer.notes else ""
            customer.notes = (customer.notes or "") + separator + notes
            updates.append(f"notes appended: '{notes}'")

        if not updates:
            return "No fields provided to update."

        logger.info("crm_updated", email=email, changes=updates)

        return (
            f"Customer record updated for {customer.name} ({email}):\n"
            + "\n".join(f"  - {u}" for u in updates)
        )


@tool
async def get_customer_info(email: str) -> str:
    """Retrieve the full CRM profile for a customer by their email."""
    async with get_session() as session:
        result = await session.execute(
            select(Customer).where(Customer.email == email)
        )
        customer = result.scalar_one_or_none()

        if not customer:
            return f"No customer found with email '{email}'."

        return (
            f"Customer Profile:\n"
            f"  ID: {customer.id}\n"
            f"  Name: {customer.name}\n"
            f"  Email: {customer.email}\n"
            f"  Phone: {customer.phone or 'Not on file'}\n"
            f"  Notes: {customer.notes or 'None'}\n"
            f"  Member since: {customer.created_at.strftime('%Y-%m-%d')}"
        )
