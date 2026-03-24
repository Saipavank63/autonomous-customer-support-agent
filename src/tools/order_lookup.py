from datetime import datetime
from typing import Optional

import structlog
from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.db.connection import get_session
from src.db.models import Customer, Order

logger = structlog.get_logger()


@tool
async def lookup_order(order_id: str) -> str:
    """Look up an order by its ID. Returns order details including status,
    items, total, tracking info, and any associated refunds."""
    async with get_session() as session:
        result = await session.execute(
            select(Order)
            .options(selectinload(Order.refunds), selectinload(Order.customer))
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()

        if not order:
            logger.info("order_not_found", order_id=order_id)
            return f"No order found with ID '{order_id}'. Please verify the order number."

        refund_lines = []
        for r in order.refunds:
            refund_lines.append(
                f"  - Refund {r.id}: ${r.amount} ({r.status.value})"
            )
        refund_section = "\n".join(refund_lines) if refund_lines else "  None"

        logger.info("order_found", order_id=order_id, status=order.status.value)
        return (
            f"Order: {order.id}\n"
            f"Customer: {order.customer.name} ({order.customer.email})\n"
            f"Status: {order.status.value}\n"
            f"Items: {order.item_summary}\n"
            f"Total: ${order.total}\n"
            f"Tracking: {order.tracking_number or 'Not available'}\n"
            f"Placed: {order.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"Refunds:\n{refund_section}"
        )


@tool
async def lookup_orders_by_email(email: str) -> str:
    """Find all orders for a customer by their email address.
    Returns a summary list of their orders."""
    async with get_session() as session:
        result = await session.execute(
            select(Customer)
            .options(selectinload(Customer.orders))
            .where(Customer.email == email)
        )
        customer = result.scalar_one_or_none()

        if not customer:
            return f"No customer found with email '{email}'."

        if not customer.orders:
            return f"Customer {customer.name} has no orders on file."

        lines = [f"Orders for {customer.name} ({customer.email}):"]
        for o in sorted(customer.orders, key=lambda x: x.created_at, reverse=True):
            lines.append(
                f"  - {o.id}: {o.status.value} | ${o.total} | {o.item_summary[:60]}"
            )

        logger.info("orders_lookup_by_email", email=email, count=len(customer.orders))
        return "\n".join(lines)
