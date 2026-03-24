# Autonomous Customer Support Agent

An AI-powered customer support agent built with LangChain's ReAct framework, capable of handling multi-step support requests end-to-end. The agent can look up orders, process refunds, update CRM records, and send SMS notifications — all through natural conversation.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Server                        │
│                 (REST + WebSocket)                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌───────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │ Guardrails│───▶│  ReAct Agent │◀──▶│   Memory     │ │
│  │  (Safety) │    │  (LangChain) │    │ (Sliding     │ │
│  │           │    │              │    │  Window +    │ │
│  │ - PII     │    │  GPT-4o      │    │  Entity      │ │
│  │ - Off-topic│   │  Tool Calling │    │  Extraction) │ │
│  │ - Injection│   │              │    │              │ │
│  └───────────┘    └──────┬───────┘    └──────────────┘ │
│                          │                              │
│            ┌─────────────┼─────────────┐               │
│            ▼             ▼             ▼               │
│     ┌────────────┐ ┌──────────┐ ┌───────────┐        │
│     │   Order    │ │  Refund  │ │    CRM    │        │
│     │   Lookup   │ │ Processor│ │   Update  │        │
│     └─────┬──────┘ └────┬─────┘ └─────┬─────┘        │
│           │              │             │               │
│           ▼              ▼             ▼               │
│     ┌──────────────────────────────────────┐          │
│     │          PostgreSQL Database          │          │
│     │  (Customers, Orders, Refunds)        │          │
│     └──────────────────────────────────────┘          │
│                                                        │
│     ┌──────────────┐                                  │
│     │    Twilio     │  SMS notifications              │
│     │   Notifier    │                                 │
│     └──────────────┘                                  │
└─────────────────────────────────────────────────────────┘
```

## Features

- **ReAct Agent**: LangChain-based agent with GPT-4o that reasons and acts through tool calls to resolve support tickets autonomously
- **Custom Tools**: Order lookup, refund processing, CRM updates, and SMS notifications — each with proper validation and error handling
- **Sliding-Window Memory**: Maintains the last N messages in context while extracting key entities (names, emails, order IDs) that persist across the full session
- **Safety Guardrails**: PII detection and redaction (credit cards, SSNs), off-topic filtering, and prompt injection defense
- **Real-time Chat**: WebSocket support for streaming conversations alongside a standard REST API
- **PostgreSQL Backend**: Full relational data model with async SQLAlchemy for orders, customers, and refunds

## Tech Stack

| Component         | Technology                          |
|-------------------|-------------------------------------|
| Agent Framework   | LangChain, LangGraph (ReAct)       |
| LLM               | GPT-4o via OpenAI API              |
| Database          | PostgreSQL + SQLAlchemy (async)     |
| API               | FastAPI with WebSocket support      |
| Notifications     | Twilio SMS                          |
| Safety            | Custom guardrails (PII, injection)  |
| Containerization  | Docker + Docker Compose             |

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (or Docker)
- OpenAI API key

### With Docker

```bash
# Clone the repo
git clone https://github.com/yourusername/autonomous-customer-support-agent.git
cd autonomous-customer-support-agent

# Configure environment
cp .env.example .env
# Edit .env with your OpenAI API key and Twilio credentials

# Start everything
docker compose up --build
```

### Local Development

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL (via Docker or local install)
docker compose up postgres -d

# Configure environment
cp .env.example .env
# Edit .env with your keys

# Run the server
uvicorn src.api.main:app --reload
```

The API will be available at `http://localhost:8000`. Interactive docs at `/docs`.

## Usage

### REST API

```bash
# Send a message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I need help with order ORD-ABC123", "session_id": "user-1"}'

# Check session state
curl http://localhost:8000/session/user-1

# Health check
curl http://localhost:8000/health
```

### WebSocket

```python
import asyncio
import websockets
import json

async def chat():
    async with websockets.connect("ws://localhost:8000/ws/my-session") as ws:
        await ws.send(json.dumps({"content": "What's the status of ORD-ABC123?"}))
        while True:
            response = json.loads(await ws.recv())
            if response["type"] == "response":
                print(response["content"])
                break

asyncio.run(chat())
```

### Example Conversation

```
User: Hi, I'm Sarah. My email is sarah@example.com and I need help with order ORD-XY7890.

Agent: Hi Sarah! Let me look up that order for you right away.
       [Looks up order ORD-XY7890]
       I can see your order ORD-XY7890 — it shows 2x Bluetooth Speakers,
       totaling $89.98, and it was delivered on March 15. How can I help?

User: One of the speakers arrived damaged. I'd like a refund for it.

Agent: I'm sorry to hear that. I can process a refund of $44.99 for the
       damaged speaker. Can you confirm that amount and I'll get it started?

User: Yes, go ahead.

Agent: [Processes refund for $44.99]
       Done! Refund REF-abc123 has been approved for $44.99. You should
       see the credit within 5-7 business days. I've also noted this on
       your account. Is there anything else I can help with?
```

## Project Structure

```
├── src/
│   ├── agent/
│   │   ├── core.py          # ReAct agent with LangChain
│   │   ├── memory.py        # Sliding-window memory + entity extraction
│   │   └── guardrails.py    # PII detection, off-topic filtering
│   ├── tools/
│   │   ├── order_lookup.py   # Order search by ID or email
│   │   ├── refund_processor.py # Refund validation and processing
│   │   ├── crm_update.py     # Customer record management
│   │   └── twilio_notifier.py # SMS notifications via Twilio
│   ├── db/
│   │   ├── models.py         # SQLAlchemy models
│   │   └── connection.py     # Async database session management
│   ├── api/
│   │   ├── main.py           # FastAPI server with WebSocket
│   │   └── schemas.py        # Pydantic request/response models
│   └── config.py             # Environment-based configuration
├── tests/
│   ├── test_agent.py         # Memory and entity extraction tests
│   ├── test_tools.py         # Tool validation logic tests
│   ├── test_guardrails.py    # Safety layer tests
│   └── conftest.py           # Shared fixtures
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Running Tests

```bash
pip install pytest pytest-asyncio aiosqlite
pytest tests/ -v
```

## Configuration

All settings are managed through environment variables (see `.env.example`):

| Variable              | Description                        | Default       |
|-----------------------|------------------------------------|---------------|
| `OPENAI_API_KEY`      | OpenAI API key                     | Required      |
| `DATABASE_URL`        | PostgreSQL connection (async)      | localhost      |
| `AGENT_MODEL`         | LLM model name                     | gpt-4o        |
| `MEMORY_WINDOW_SIZE`  | Messages kept in sliding window    | 20            |
| `MAX_REFUND_AMOUNT`   | Auto-approval refund limit ($)     | 500.00        |
| `TWILIO_ACCOUNT_SID`  | Twilio SID for SMS                 | Optional      |
| `TWILIO_AUTH_TOKEN`   | Twilio auth token                  | Optional      |
| `TWILIO_FROM_NUMBER`  | Twilio sender number               | Optional      |
