from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.db.models import Customer, Order, OrderStatus, Refund, RefundStatus
from src.tools.refund_processor import _validate_refund_request


class TestRefundValidation:
    """Test refund business rules without hitting the database."""

    def _make_order(self, status=OrderStatus.DELIVERED, total="100.00", refunds=None):
        order = MagicMock(spec=Order)
        order.id = "ORD-TEST01"
        order.status = status
        order.total = Decimal(total)
        order.refunds = refunds or []
        return order

    def test_allows_refund_on_delivered_order(self):
        order = self._make_order(status=OrderStatus.DELIVERED)
        ok, msg = _validate_refund_request(order, Decimal("50.00"))
        assert ok is True

    def test_rejects_refund_on_pending_order(self):
        order = self._make_order(status=OrderStatus.PENDING)
        ok, msg = _validate_refund_request(order, Decimal("10.00"))
        assert ok is False
        assert "not eligible" in msg.lower()

    def test_rejects_refund_on_cancelled_order(self):
        order = self._make_order(status=OrderStatus.CANCELLED)
        ok, msg = _validate_refund_request(order, Decimal("10.00"))
        assert ok is False

    def test_rejects_amount_exceeding_order_total(self):
        order = self._make_order(total="50.00")
        ok, msg = _validate_refund_request(order, Decimal("75.00"))
        assert ok is False
        assert "exceeds" in msg.lower()

    def test_accounts_for_existing_refunds(self):
        existing = MagicMock(spec=Refund)
        existing.amount = Decimal("80.00")
        existing.status = RefundStatus.APPROVED

        order = self._make_order(total="100.00", refunds=[existing])
        ok, msg = _validate_refund_request(order, Decimal("30.00"))
        assert ok is False
        assert "remaining" in msg.lower()

    def test_ignores_denied_refunds_in_total(self):
        denied = MagicMock(spec=Refund)
        denied.amount = Decimal("100.00")
        denied.status = RefundStatus.DENIED

        order = self._make_order(total="100.00", refunds=[denied])
        ok, msg = _validate_refund_request(order, Decimal("50.00"))
        assert ok is True

    @patch("src.tools.refund_processor.settings")
    def test_rejects_amount_exceeding_auto_approval_limit(self, mock_settings):
        mock_settings.max_refund_amount = 100.00
        order = self._make_order(total="1000.00")
        ok, msg = _validate_refund_request(order, Decimal("200.00"))
        assert ok is False
        assert "auto-approval limit" in msg.lower()


class TestTwilioNotifier:
    @pytest.mark.asyncio
    async def test_rejects_invalid_phone_format(self):
        from src.tools.twilio_notifier import send_sms_notification

        result = await send_sms_notification.ainvoke({
            "phone_number": "5551234567",
            "message": "Test",
        })
        assert "invalid" in result.lower()

    @pytest.mark.asyncio
    async def test_rejects_oversized_message(self):
        from src.tools.twilio_notifier import send_sms_notification

        result = await send_sms_notification.ainvoke({
            "phone_number": "+15551234567",
            "message": "x" * 1601,
        })
        assert "1600" in result
