import uuid
from datetime import datetime
from decimal import Decimal
from typing import Set, Tuple

import structlog
from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.config import settings
from src.db.connection import get_session
from src.db.models import Order, OrderStatus, Refund, RefundStatus

logger = structlog.get_logger()

REFUNDABLE_STATUSES: Set[OrderStatus] = {
    OrderStatus.CONFIRMED,
    OrderStatus.SHIPPED,
    OrderStatus.DELIVERED,
}


def _validate_refund_request(
    order: Order, amount: Decimal
) -> Tuple[bool, str]:
    """Run business-rule checks before approving a refund."""
    if order.status not in REFUNDABLE_STATUSES:
        return False, (
            f"Order {order.id} has status '{order.status.value}' and is not eligible "
            f"for refund. Refunds are available for confirmed, shipped, or delivered orders."
        )

    existing_refund_total = sum(
        r.amount for r in order.refunds if r.status != RefundStatus.DENIED
    )
    remaining = order.total - existing_refund_total

    if amount > remaining:
        return False, (
            f"Requested refund ${amount} exceeds the remaining refundable amount "
            f"of ${remaining:.2f} on order {order.id}."
        )

    if amount > Decimal(str(settings.max_refund_amount)):
        return False, (
            f"Refund of ${amount} exceeds the auto-approval limit of "
            f"${settings.max_refund_amount:.2f}. This needs manual manager approval."
        )

    return True, ""


@tool
async def process_refund(order_id: str, amount: str, reason: str) -> str:
    """Process a refund for a given order. Validates the order is eligible,
    checks refund limits, and creates a refund record.

    Args:
        order_id: The order ID to refund.
        amount: Dollar amount to refund (e.g. '29.99').
        reason: Customer-provided reason for the refund.
    """
    try:
        refund_amount = Decimal(amount)
    except Exception:
        return f"Invalid amount '{amount}'. Provide a numeric value like '29.99'."

    if refund_amount <= 0:
        return "Refund amount must be greater than zero."

    async with get_session() as session:
        result = await session.execute(
            select(Order)
            .options(selectinload(Order.refunds))
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()

        if not order:
            return f"Order '{order_id}' not found. Cannot process refund."

        eligible, rejection_msg = _validate_refund_request(order, refund_amount)
        if not eligible:
            logger.warning(
                "refund_rejected",
                order_id=order_id,
                amount=str(refund_amount),
                reason=rejection_msg,
            )
            return rejection_msg

        refund = Refund(
            id=str(uuid.uuid4()),
            order_id=order_id,
            amount=refund_amount,
            reason=reason,
            status=RefundStatus.APPROVED,
            processed_at=datetime.utcnow(),
        )
        session.add(refund)

        logger.info(
            "refund_processed",
            refund_id=refund.id,
            order_id=order_id,
            amount=str(refund_amount),
        )

        return (
            f"Refund approved and processed.\n"
            f"Refund ID: {refund.id}\n"
            f"Amount: ${refund_amount}\n"
            f"Order: {order_id}\n"
            f"The customer should see the credit within 5-7 business days."
        )


@tool
async def check_refund_status(refund_id: str) -> str:
    """Check the current status of a refund by its ID."""
    async with get_session() as session:
        result = await session.execute(
            select(Refund).where(Refund.id == refund_id)
        )
        refund = result.scalar_one_or_none()

        if not refund:
            return f"No refund found with ID '{refund_id}'."

        return (
            f"Refund {refund.id}:\n"
            f"  Status: {refund.status.value}\n"
            f"  Amount: ${refund.amount}\n"
            f"  Order: {refund.order_id}\n"
            f"  Reason: {refund.reason}\n"
            f"  Processed: {refund.processed_at.strftime('%Y-%m-%d %H:%M') if refund.processed_at else 'Pending'}"
        )
