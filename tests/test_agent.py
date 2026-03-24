import pytest

from src.agent.memory import EntityStore, SlidingWindowMemory, _extract_entities_from_text


class TestEntityExtraction:
    def test_extracts_email(self):
        store = EntityStore()
        _extract_entities_from_text("My email is jane@example.com", store)
        assert store.customer_email == "jane@example.com"

    def test_extracts_order_id(self):
        store = EntityStore()
        _extract_entities_from_text("I need help with order ORD-ABC123", store)
        assert "ORD-ABC123" in store.order_ids

    def test_extracts_phone(self):
        store = EntityStore()
        _extract_entities_from_text("Call me at +15551234567", store)
        assert store.customer_phone == "+15551234567"

    def test_extracts_name_from_intro(self):
        store = EntityStore()
        _extract_entities_from_text("Hi, my name is John Smith", store)
        assert store.customer_name == "John Smith"

    def test_extracts_name_from_i_am(self):
        store = EntityStore()
        _extract_entities_from_text("I'm Sarah Connor and I have a problem", store)
        assert store.customer_name == "Sarah Connor"

    def test_does_not_duplicate_order_ids(self):
        store = EntityStore()
        _extract_entities_from_text("Order ORD-XYZ789 is late", store)
        _extract_entities_from_text("Can you check ORD-XYZ789 again?", store)
        assert store.order_ids.count("ORD-XYZ789") == 1


class TestSlidingWindowMemory:
    def test_basic_add_and_retrieve(self):
        mem = SlidingWindowMemory(window_size=10)
        mem.add_user_message("Hello")
        mem.add_ai_message("Hi there!")

        messages = mem.get_messages()
        # system context + 2 messages
        assert len(messages) == 3

    def test_window_trims_old_messages(self):
        mem = SlidingWindowMemory(window_size=4)
        for i in range(6):
            mem.add_user_message(f"Message {i}")

        # should only keep the last 4 user messages + 1 system context
        messages = mem.get_messages()
        assert len(messages) == 5
        assert "Message 2" in messages[1].content
        assert "Message 5" in messages[-1].content

    def test_entity_persists_after_trim(self):
        mem = SlidingWindowMemory(window_size=2)
        mem.add_user_message("My email is alice@test.com")
        mem.add_user_message("padding 1")
        mem.add_user_message("padding 2")
        mem.add_user_message("What about my order?")

        # email should still be in the entity store
        assert mem.entities.customer_email == "alice@test.com"
        # and in the system context message
        context_msg = mem.get_messages()[0]
        assert "alice@test.com" in context_msg.content

    def test_clear_resets_everything(self):
        mem = SlidingWindowMemory()
        mem.add_user_message("I'm Bob, email bob@test.com")
        mem.clear()

        assert len(mem.messages) == 0
        assert mem.entities.customer_name is None
        assert mem.entities.customer_email is None

    def test_entity_summary_format(self):
        store = EntityStore(
            customer_name="Jane",
            customer_email="jane@test.com",
            order_ids=["ORD-111111"],
        )
        summary = store.summary()
        assert "Jane" in summary
        assert "jane@test.com" in summary
        assert "ORD-111111" in summary
