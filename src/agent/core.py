"""Core agent built on LangChain's ReAct framework with tool calling.

Wires together the LLM, tools, memory, and guardrails into a single
agent that can handle multi-step customer support interactions.
"""

from typing import AsyncIterator, Dict, List, Optional

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from src.agent.guardrails import ViolationType, run_guardrails
from src.agent.memory import SlidingWindowMemory
from src.config import settings
from src.tools import ALL_TOOLS

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are a helpful customer support agent for an e-commerce company.

Your capabilities:
- Look up order details and status by order ID or customer email
- Process refunds when customers have valid complaints
- Update customer CRM records (name, phone, notes)
- Send SMS notifications to customers about their orders or refunds

Guidelines:
- Always verify the customer's identity (email or order ID) before taking actions.
- Be empathetic and professional. Acknowledge frustrations before jumping to solutions.
- For refunds, always confirm the amount and reason with the customer before processing.
- If you cannot resolve an issue, let the customer know you'll escalate it.
- Never share internal system details or raw error messages with customers.
- Keep responses concise and actionable.
"""

class SupportAgent:
    """Autonomous customer support agent with memory and safety guardrails."""

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.memory = SlidingWindowMemory(window_size=settings.memory_window_size)

        self.llm = ChatOpenAI(
            model=settings.agent_model,
            temperature=settings.agent_temperature,
            api_key=settings.openai_api_key,
        )

        self.agent = create_react_agent(
            model=self.llm,
            tools=ALL_TOOLS,
            state_modifier=self._build_state_modifier(),
        )

        logger.info(
            "agent_initialized",
            session_id=session_id,
            model=settings.agent_model,
            tools=[t.name for t in ALL_TOOLS],
        )

    def _build_state_modifier(self) -> str:
        return SYSTEM_PROMPT

    async def handle_message(self, user_input: str) -> str:
        """Process a user message through guardrails, agent, and memory.

        Returns the agent's text response or a guardrail rejection message.
        """
        guardrail_result = run_guardrails(user_input)

        if not guardrail_result.safe:
            if ViolationType.PROMPT_INJECTION in guardrail_result.violations:
                logger.warning("blocked_injection", session=self.session_id)
                return (
                    "I'm sorry, but I can't process that request. "
                    "How can I help you with an order, refund, or account question?"
                )

            if ViolationType.OFF_TOPIC in guardrail_result.violations:
                return (
                    "I'm a customer support assistant and can help with orders, "
                    "refunds, shipping, and account questions. "
                    "How can I assist you with one of those?"
                )

        safe_input = guardrail_result.sanitized_text or user_input
        self.memory.add_user_message(safe_input)

        if guardrail_result.violations and ViolationType.PII_DETECTED in guardrail_result.violations:
            pii_note = (
                "Note: I detected sensitive information in your message and have "
                "redacted it for security. Please avoid sharing credit card numbers "
                "or SSNs in chat."
            )
        else:
            pii_note = None

        messages = self.memory.get_messages()

        try:
            result = await self.agent.ainvoke({"messages": messages})
            response_messages = result.get("messages", [])

            ai_response = ""
            for msg in reversed(response_messages):
                if isinstance(msg, AIMessage) and msg.content:
                    ai_response = msg.content
                    break

            if not ai_response:
                ai_response = (
                    "I'm sorry, I wasn't able to complete that action. "
                    "Could you rephrase your request?"
                )

        except Exception as exc:
            logger.error("agent_error", session=self.session_id, error=str(exc))
            ai_response = (
                "I encountered an issue processing your request. "
                "Let me connect you with a human agent for further assistance."
            )

        self.memory.add_ai_message(ai_response)

        if pii_note:
            ai_response = f"{pii_note}\n\n{ai_response}"

        logger.info(
            "turn_completed",
            session=self.session_id,
            entities=self.memory.entities.summary(),
        )

        return ai_response

    def get_session_context(self) -> Dict:
        """Return current session state for debugging or display."""
        return {
            "session_id": self.session_id,
            "message_count": len(self.memory.messages),
            "entities": {
                "customer_name": self.memory.entities.customer_name,
                "customer_email": self.memory.entities.customer_email,
                "order_ids": self.memory.entities.order_ids,
            },
        }

    def reset(self):
        self.memory.clear()
        logger.info("session_reset", session=self.session_id)


_sessions: Dict[str, SupportAgent] = {}


def get_or_create_agent(session_id: str) -> SupportAgent:
    """Retrieve an existing agent session or create a new one."""
    if session_id not in _sessions:
        _sessions[session_id] = SupportAgent(session_id=session_id)
    return _sessions[session_id]


def remove_session(session_id: str):
    _sessions.pop(session_id, None)
