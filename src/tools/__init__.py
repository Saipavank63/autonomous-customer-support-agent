"""Tool registry for the customer support agent.

Centralises all LangChain tool imports so the agent core and any future
consumers can simply do:

    from src.tools import ALL_TOOLS

Each tool module is responsible for its own implementation; this package
re-exports the decorated functions and provides a flat list for the agent.
"""

from typing import List

from langchain_core.tools import BaseTool

from src.tools.crm_update import get_customer_info, update_customer_info
from src.tools.order_lookup import lookup_order, lookup_orders_by_email
from src.tools.refund_processor import check_refund_status, process_refund
from src.tools.twilio_notifier import send_sms_notification

ALL_TOOLS: List[BaseTool] = [
    lookup_order,
    lookup_orders_by_email,
    process_refund,
    check_refund_status,
    update_customer_info,
    get_customer_info,
    send_sms_notification,
]

__all__ = [
    "ALL_TOOLS",
    "lookup_order",
    "lookup_orders_by_email",
    "process_refund",
    "check_refund_status",
    "update_customer_info",
    "get_customer_info",
    "send_sms_notification",
]
