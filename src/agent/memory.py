"""Sliding-window conversation memory with entity extraction.

Keeps the last N messages in a buffer while extracting and persisting
key entities (customer names, emails, order IDs) so the agent can
reference them even after older messages rotate out.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage


@dataclass
class EntityStore:
    """Tracks entities extracted from the conversation."""

    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    order_ids: List[str] = field(default_factory=list)
    refund_ids: List[str] = field(default_factory=list)
    custom: Dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        parts = []
        if self.customer_name:
            parts.append(f"Customer name: {self.customer_name}")
        if self.customer_email:
            parts.append(f"Email: {self.customer_email}")
        if self.customer_phone:
            parts.append(f"Phone: {self.customer_phone}")
        if self.order_ids:
            parts.append(f"Referenced orders: {', '.join(self.order_ids)}")
        if self.refund_ids:
            parts.append(f"Referenced refunds: {', '.join(self.refund_ids)}")
        for k, v in self.custom.items():
            parts.append(f"{k}: {v}")
        return "; ".join(parts) if parts else "No extracted entities yet."


EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"\+?1?\d{9,15}")
ORDER_ID_RE = re.compile(r"ORD-[A-Z0-9]{6,}")
REFUND_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
NAME_INTRO_RE = re.compile(
    r"(?:my name is|i'm|i am|this is)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?)",
    re.IGNORECASE,
)


def _extract_entities_from_text(text: str, store: EntityStore):
    """Pull structured entities out of a free-text message."""
    email_match = EMAIL_RE.search(text)
    if email_match:
        store.customer_email = email_match.group()

    phone_match = PHONE_RE.search(text)
    if phone_match and len(phone_match.group()) >= 10:
        store.customer_phone = phone_match.group()

    for oid in ORDER_ID_RE.findall(text):
        if oid not in store.order_ids:
            store.order_ids.append(oid)

    for rid in REFUND_ID_RE.findall(text):
        if rid not in store.refund_ids:
            store.refund_ids.append(rid)

    name_match = NAME_INTRO_RE.search(text)
    if name_match:
        store.customer_name = name_match.group(1).strip()


class SlidingWindowMemory:
    """Maintains a fixed-size window of conversation messages while
    extracting entities into a persistent store that outlives the window.

    The entity summary is injected as a system message at the start of
    the message list so the agent always has access to key context.
    """

    def __init__(self, window_size: int = 20):
        self.window_size = window_size
        self.messages: List[BaseMessage] = []
        self.entities = EntityStore()

    def add_user_message(self, content: str):
        _extract_entities_from_text(content, self.entities)
        self.messages.append(HumanMessage(content=content))
        self._trim()

    def add_ai_message(self, content: str):
        _extract_entities_from_text(content, self.entities)
        self.messages.append(AIMessage(content=content))
        self._trim()

    def add_message(self, message: BaseMessage):
        if hasattr(message, "content") and isinstance(message.content, str):
            _extract_entities_from_text(message.content, self.entities)
        self.messages.append(message)
        self._trim()

    def get_messages(self) -> List[BaseMessage]:
        """Return the current window with an entity context preamble."""
        entity_summary = self.entities.summary()
        context_msg = SystemMessage(
            content=(
                f"Extracted session context: {entity_summary}\n"
                "Use this context to maintain continuity even if earlier "
                "messages have scrolled out of the conversation window."
            )
        )
        return [context_msg] + list(self.messages)

    def clear(self):
        self.messages.clear()
        self.entities = EntityStore()

    def _trim(self):
        if len(self.messages) > self.window_size:
            self.messages = self.messages[-self.window_size :]
