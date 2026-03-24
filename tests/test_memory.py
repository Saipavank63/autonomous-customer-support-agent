"""Comprehensive tests for sliding-window memory and entity persistence.

Covers window trimming behaviour, entity extraction edge cases, entity
persistence after messages rotate out, session clearing, and the context
preamble that is injected into the message list.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agent.memory import (
    EntityStore,
    SlidingWindowMemory,
    _extract_entities_from_text,
)


# ── Window size limits ──────────────────────────────────────────────────

class TestWindowSizeLimits:
    """Ensure the sliding window never exceeds the configured capacity."""

    def test_window_enforces_exact_limit(self):
        mem = SlidingWindowMemory(window_size=3)
        for i in range(10):
            mem.add_user_message(f"msg-{i}")
        assert len(mem.messages) == 3

    def test_alternating_user_ai_respects_limit(self):
        mem = SlidingWindowMemory(window_size=4)
        for i in range(6):
            mem.add_user_message(f"user-{i}")
            mem.add_ai_message(f"bot-{i}")
        # 12 total added, only 4 survive
        assert len(mem.messages) == 4

    def test_oldest_messages_are_dropped(self):
        mem = SlidingWindowMemory(window_size=3)
        mem.add_user_message("first")
        mem.add_user_message("second")
        mem.add_user_message("third")
        mem.add_user_message("fourth")

        contents = [m.content for m in mem.messages]
        assert "first" not in contents
        assert "fourth" in contents
        assert "second" in contents  # second, third, fourth survive

    def test_window_size_one(self):
        mem = SlidingWindowMemory(window_size=1)
        mem.add_user_message("a")
        mem.add_user_message("b")
        assert len(mem.messages) == 1
        assert mem.messages[0].content == "b"

    def test_get_messages_includes_system_context(self):
        """get_messages() prepends a system context message to the window."""
        mem = SlidingWindowMemory(window_size=5)
        mem.add_user_message("hello")
        messages = mem.get_messages()
        # system context + 1 user message
        assert len(messages) == 2
        assert isinstance(messages[0], SystemMessage)

    def test_raw_messages_list_excludes_system_context(self):
        mem = SlidingWindowMemory(window_size=5)
        mem.add_user_message("hello")
        # .messages is just the buffer, no system context
        assert len(mem.messages) == 1


# ── Entity persistence after window trim ────────────────────────────────

class TestEntityPersistenceAfterTrim:
    """Entities extracted from early messages must survive window trimming."""

    def test_email_persists_after_trim(self):
        mem = SlidingWindowMemory(window_size=2)
        mem.add_user_message("My email is alice@example.com")
        # Push the original message out of the window
        mem.add_user_message("filler 1")
        mem.add_user_message("filler 2")
        mem.add_user_message("filler 3")

        assert mem.entities.customer_email == "alice@example.com"
        # Email should appear in the system context preamble
        context = mem.get_messages()[0].content
        assert "alice@example.com" in context

    def test_name_persists_after_trim(self):
        mem = SlidingWindowMemory(window_size=2)
        mem.add_user_message("Hi, my name is Jane Doe")
        mem.add_user_message("padding")
        mem.add_user_message("padding")
        mem.add_user_message("What is my order status?")

        assert mem.entities.customer_name == "Jane Doe"

    def test_order_id_persists_after_trim(self):
        mem = SlidingWindowMemory(window_size=2)
        mem.add_user_message("Check order ORD-ABC123 please")
        mem.add_user_message("x")
        mem.add_user_message("x")

        assert "ORD-ABC123" in mem.entities.order_ids

    def test_multiple_order_ids_persist(self):
        mem = SlidingWindowMemory(window_size=2)
        mem.add_user_message("Order ORD-AAA111 was late")
        mem.add_user_message("Also check ORD-BBB222")
        mem.add_user_message("filler")
        mem.add_user_message("filler")

        assert "ORD-AAA111" in mem.entities.order_ids
        assert "ORD-BBB222" in mem.entities.order_ids

    def test_phone_persists_after_trim(self):
        mem = SlidingWindowMemory(window_size=2)
        mem.add_user_message("Call me at +15559876543")
        mem.add_user_message("filler")
        mem.add_user_message("filler")

        assert mem.entities.customer_phone == "+15559876543"

    def test_ai_message_entities_also_persist(self):
        """Entities extracted from AI responses should persist too."""
        mem = SlidingWindowMemory(window_size=2)
        mem.add_ai_message(
            "I found your order ORD-XYZ999. It was delivered yesterday."
        )
        mem.add_user_message("filler")
        mem.add_user_message("filler")

        assert "ORD-XYZ999" in mem.entities.order_ids


# ── Session clearing ────────────────────────────────────────────────────

class TestSessionClearing:
    """clear() must reset both the message buffer and the entity store."""

    def test_clear_empties_messages(self):
        mem = SlidingWindowMemory(window_size=10)
        for i in range(5):
            mem.add_user_message(f"msg-{i}")
        mem.clear()
        assert len(mem.messages) == 0

    def test_clear_resets_entities(self):
        mem = SlidingWindowMemory(window_size=10)
        mem.add_user_message("I'm Bob, email bob@test.com, order ORD-CLEAR1")
        mem.clear()

        assert mem.entities.customer_name is None
        assert mem.entities.customer_email is None
        assert mem.entities.order_ids == []
        assert mem.entities.refund_ids == []

    def test_clear_resets_entity_summary(self):
        mem = SlidingWindowMemory(window_size=10)
        mem.add_user_message("My email is x@y.com")
        mem.clear()

        summary = mem.entities.summary()
        assert summary == "No extracted entities yet."

    def test_new_messages_after_clear_work_normally(self):
        mem = SlidingWindowMemory(window_size=5)
        mem.add_user_message("First session message")
        mem.clear()
        mem.add_user_message("New session, my email is fresh@start.com")

        assert len(mem.messages) == 1
        assert mem.entities.customer_email == "fresh@start.com"


# ── Entity extraction edge cases ────────────────────────────────────────

class TestEntityExtractionEdgeCases:
    def test_no_entities_in_generic_text(self):
        store = EntityStore()
        _extract_entities_from_text("I just have a general question", store)
        assert store.customer_email is None
        assert store.customer_name is None
        assert store.order_ids == []

    def test_email_overwrites_with_latest(self):
        store = EntityStore()
        _extract_entities_from_text("Email is first@test.com", store)
        _extract_entities_from_text("Actually use second@test.com", store)
        assert store.customer_email == "second@test.com"

    def test_name_overwrites_with_latest(self):
        store = EntityStore()
        _extract_entities_from_text("My name is Alice Smith", store)
        _extract_entities_from_text("I'm Bob Jones", store)
        assert store.customer_name == "Bob Jones"

    def test_duplicate_order_ids_not_added(self):
        store = EntityStore()
        _extract_entities_from_text("Order ORD-DUP123", store)
        _extract_entities_from_text("Order ORD-DUP123 again", store)
        assert store.order_ids.count("ORD-DUP123") == 1

    def test_refund_id_extraction(self):
        store = EntityStore()
        _extract_entities_from_text(
            "Refund ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890", store
        )
        assert "a1b2c3d4-e5f6-7890-abcd-ef1234567890" in store.refund_ids

    def test_multiple_entities_in_single_message(self):
        store = EntityStore()
        _extract_entities_from_text(
            "I'm Sarah Lee, email sarah@shop.com, order ORD-MULTI1 and ORD-MULTI2",
            store,
        )
        assert store.customer_name == "Sarah Lee"
        assert store.customer_email == "sarah@shop.com"
        assert "ORD-MULTI1" in store.order_ids
        assert "ORD-MULTI2" in store.order_ids


# ── EntityStore summary formatting ──────────────────────────────────────

class TestEntityStoreSummary:
    def test_empty_store_summary(self):
        store = EntityStore()
        assert store.summary() == "No extracted entities yet."

    def test_partial_store_summary(self):
        store = EntityStore(customer_email="test@example.com")
        summary = store.summary()
        assert "test@example.com" in summary
        # Name should NOT appear since it's None
        assert "Customer name" not in summary

    def test_full_store_summary(self):
        store = EntityStore(
            customer_name="Test User",
            customer_email="test@test.com",
            customer_phone="+15551112222",
            order_ids=["ORD-A", "ORD-B"],
            refund_ids=["ref-1"],
        )
        summary = store.summary()
        assert "Test User" in summary
        assert "test@test.com" in summary
        assert "+15551112222" in summary
        assert "ORD-A" in summary
        assert "ORD-B" in summary
        assert "ref-1" in summary

    def test_custom_entities_in_summary(self):
        store = EntityStore(custom={"preferred_language": "Spanish"})
        summary = store.summary()
        assert "preferred_language" in summary
        assert "Spanish" in summary


# ── add_message (generic BaseMessage) ───────────────────────────────────

class TestAddGenericMessage:
    def test_add_human_message_object(self):
        mem = SlidingWindowMemory(window_size=5)
        mem.add_message(HumanMessage(content="Hi from object"))
        assert len(mem.messages) == 1
        assert mem.messages[0].content == "Hi from object"

    def test_add_ai_message_object(self):
        mem = SlidingWindowMemory(window_size=5)
        mem.add_message(AIMessage(content="Reply from object"))
        assert len(mem.messages) == 1

    def test_add_message_extracts_entities(self):
        mem = SlidingWindowMemory(window_size=5)
        mem.add_message(HumanMessage(content="My email is via@add.com"))
        assert mem.entities.customer_email == "via@add.com"

    def test_add_message_respects_window(self):
        mem = SlidingWindowMemory(window_size=2)
        mem.add_message(HumanMessage(content="a"))
        mem.add_message(HumanMessage(content="b"))
        mem.add_message(HumanMessage(content="c"))
        assert len(mem.messages) == 2
        assert mem.messages[0].content == "b"
