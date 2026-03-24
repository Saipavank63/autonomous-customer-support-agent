# Autonomous Customer Support Agent

An AI-powered customer support agent built with LangChain's ReAct framework, capable of handling multi-step support requests end-to-end. The agent can look up orders, process refunds, update CRM records, and send SMS notifications — all through natural conversation.

## Architecture

```
                          ┌──────────────────────┐
                          │    Client (REST /     │
                          │   WebSocket / cURL)   │
                          └──────────┬───────────┘
                                     │
                ┌────────────────────▼────────────────────┐
                │          FastAPI Application             │
                │  ┌─────────────┐  ┌──────────────────┐  │
                │  │  Request    │  │   Rate Limiter   │  │
                │  │  Logger     │  │  (token bucket)  │  │
                │  └──────┬──────┘  └────────┬─────────┘  │
                │         └────────┬─────────┘            │
                │                  ▼                      │
                │  ┌──────────────────────────────────┐   │
                │  │          Guardrails Layer         │   │
                │  │   PII redaction · Off-topic       │   │
                │  │   filter · Injection defense      │   │
                │  └──────────────┬───────────────────┘   │
                │                 ▼                       │
                │  ┌──────────────────────────────────┐   │
                │  │       ReAct Agent (LangGraph)     │   │
                │  │         GPT-4o · Tool Calling     │   │
                │  └─────┬─────┬──────┬─────┬─────────┘   │
                │        │     │      │     │             │
                │   ┌────▼─┐ ┌▼────┐ ┌▼───┐ ┌▼────────┐  │
                │   │Order │ │Refund│ │CRM │ │ Twilio  │  │
                │   │Lookup│ │Proc. │ │Upd.│ │Notifier │  │
                │   └──┬───┘ └──┬──┘ └─┬──┘ └─────────┘  │
                │      └────────┼──────┘                  │
                │               ▼                         │
                │  ┌──────────────────────────────────┐   │
                │  │       PostgreSQL Database          │   │
                │  │   Customers · Orders · Refunds    │   │
                │  └──────────────────────────────────┘   │
                │                                         │
                │  ┌──────────────────────────────────┐   │
                │  │   Sliding-Window Memory            │   │
                │  │   Message buffer + Entity store    │   │
                │  └──────────────────────────────────┘   │
                └─────────────────────────────────────────┘
```

## Features

- **ReAct Agent**: LangChain-based agent with GPT-4o that reasons and acts through tool calls to resolve support tickets autonomously
- **Custom Tools**: Order lookup, refund processing, CRM updates, and SMS notifications — each with proper validation and error handling
- **Sliding-Window Memory**: Maintains the last N messages in context while extracting key entities (names, emails, order IDs) that persist across the full session
- **Safety Guardrails**: PII detection and redaction (credit cards, SSNs), off-topic filtering, and prompt injection defense
- **Real-time Chat**: WebSocket support for streaming conversations alongside a standard REST API
- **Request Middleware**: Structured request logging with timing and per-IP token-bucket rate limiting
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

### 1. Clone and configure

```bash
git clone https://github.com/yourusername/autonomous-customer-support-agent.git
cd autonomous-customer-support-agent
cp .env.example .env
# Open .env and set your OPENAI_API_KEY (required).
# Twilio credentials are optional — the agent works without them.
```

### 2a. Run with Docker (recommended)

```bash
make docker-up        # builds the image, starts app + Postgres
# API is live at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

### 2b. Run locally

```bash
python -m venv .venv && source .venv/bin/activate
make install          # pip install -r requirements.txt
make db-up            # start Postgres in Docker
make dev              # uvicorn with --reload
```

### 3. Send your first message

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hi, I need help with order ORD-ABC123", "session_id": "demo"}'
```

### 4. Run the tests

```bash
make test
```

## API Reference

### REST Endpoints

| Method   | Path                    | Description                                | Request Body                    | Response                |
|----------|-------------------------|--------------------------------------------|---------------------------------|-------------------------|
| `GET`    | `/health`               | Liveness probe                             | —                               | `HealthResponse`        |
| `POST`   | `/chat`                 | Send a message and get the agent's reply   | `ChatRequest`                   | `ChatResponse`          |
| `GET`    | `/session/{session_id}` | Inspect current session state and entities | —                               | `SessionInfo`           |
| `DELETE` | `/session/{session_id}` | Clear and remove a conversation session    | —                               | `{"status": "deleted"}` |

### WebSocket

| Path                   | Description                              |
|------------------------|------------------------------------------|
| `/ws/{session_id}`     | Real-time bidirectional chat channel     |

**WebSocket message flow:**

```
Client  ──▶  {"content": "Where is my order?"}
Server  ◀──  {"type": "status", "content": "thinking"}
Server  ◀──  {"type": "response", "content": "...", "entities": {...}}
```

### Request / Response Schemas

**ChatRequest**
```json
{
  "message": "string (1-2000 chars, required)",
  "session_id": "string (max 100 chars, default: 'default')"
}
```

**ChatResponse**
```json
{
  "response": "Agent's reply text",
  "session_id": "demo",
  "entities": {
    "customer_name": "Sarah",
    "customer_email": "sarah@example.com",
    "order_ids": ["ORD-ABC123"]
  },
  "guardrail_flags": []
}
```

### Rate Limiting

The API applies a per-IP token-bucket rate limit (default: 60 requests/min with burst of 20). Rate limit headers are included in every response:

| Header                   | Description                  |
|--------------------------|------------------------------|
| `X-RateLimit-Limit`      | Requests allowed per minute  |
| `X-RateLimit-Remaining`  | Tokens remaining in bucket   |
| `Retry-After`            | Seconds to wait (on 429)     |

## Usage

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

### WebSocket Client (Python)

```python
import asyncio, json, websockets

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

## Project Structure

```
├── src/
│   ├── agent/
│   │   ├── core.py          # ReAct agent with LangChain
│   │   ├── memory.py        # Sliding-window memory + entity extraction
│   │   └── guardrails.py    # PII detection, off-topic filtering
│   ├── tools/
│   │   ├── __init__.py      # Tool registry — exports ALL_TOOLS
│   │   ├── order_lookup.py  # Order search by ID or email
│   │   ├── refund_processor.py # Refund validation and processing
│   │   ├── crm_update.py    # Customer record management
│   │   └── twilio_notifier.py # SMS notifications via Twilio
│   ├── db/
│   │   ├── models.py        # SQLAlchemy models
│   │   └── connection.py    # Async database session management
│   ├── api/
│   │   ├── main.py          # FastAPI server with WebSocket
│   │   ├── schemas.py       # Pydantic request/response models
│   │   └── middleware.py    # Request logging + rate limiting
│   └── config.py            # Environment-based configuration
├── tests/
│   ├── test_agent.py        # Memory and entity extraction tests
│   ├── test_memory.py       # Comprehensive sliding-window memory tests
│   ├── test_tools.py        # Tool validation logic tests
│   ├── test_guardrails.py   # Safety layer tests
│   └── conftest.py          # Shared fixtures
├── Makefile                 # Common dev commands (make help)
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Running Tests

```bash
# Quick run
make test

# With coverage
make test-cov
```

## Configuration

All settings are managed through environment variables (see `.env.example`):

| Variable              | Description                        | Default       |
|-----------------------|------------------------------------|---------------|
| `OPENAI_API_KEY`      | OpenAI API key                     | **Required**  |
| `DATABASE_URL`        | PostgreSQL connection (async)      | localhost      |
| `AGENT_MODEL`         | LLM model name                     | gpt-4o        |
| `AGENT_TEMPERATURE`   | LLM temperature (0-1)             | 0.1           |
| `MEMORY_WINDOW_SIZE`  | Messages kept in sliding window    | 20            |
| `MAX_REFUND_AMOUNT`   | Auto-approval refund limit ($)     | 500.00        |
| `TWILIO_ACCOUNT_SID`  | Twilio SID for SMS                 | Optional      |
| `TWILIO_AUTH_TOKEN`   | Twilio auth token                  | Optional      |
| `TWILIO_FROM_NUMBER`  | Twilio sender number               | Optional      |
| `APP_ENV`             | `development` or `production`      | development   |
| `LOG_LEVEL`           | Python log level                   | INFO          |
| `API_HOST`            | Server bind address                | 0.0.0.0       |
| `API_PORT`            | Server port                        | 8000          |
