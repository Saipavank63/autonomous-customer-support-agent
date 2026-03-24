import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.agent.core import get_or_create_agent, remove_session
from src.api.middleware import RateLimitMiddleware, RequestLoggingMiddleware
from src.api.schemas import ChatRequest, ChatResponse, HealthResponse, SessionInfo
from src.db.connection import close_db, init_db

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("app_started")
    yield
    await close_db()
    logger.info("app_stopped")


app = FastAPI(
    title="Autonomous Customer Support Agent",
    description="AI-powered customer support with order lookup, refunds, and CRM integration.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60, burst=20)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc),
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to the support agent and get a response."""
    agent = get_or_create_agent(request.session_id)
    response_text = await agent.handle_message(request.message)
    context = agent.get_session_context()

    return ChatResponse(
        response=response_text,
        session_id=request.session_id,
        entities=context.get("entities", {}),
    )


@app.get("/session/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    """Get the current state of a conversation session."""
    agent = get_or_create_agent(session_id)
    context = agent.get_session_context()
    return SessionInfo(**context)


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Clear and remove a conversation session."""
    remove_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@app.websocket("/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat sessions."""
    await websocket.accept()
    agent = get_or_create_agent(session_id)
    logger.info("ws_connected", session_id=session_id)

    try:
        while True:
            data = await websocket.receive_text()

            try:
                payload = json.loads(data)
                user_message = payload.get("content", data)
            except json.JSONDecodeError:
                user_message = data

            await websocket.send_json({
                "type": "status",
                "content": "thinking",
            })

            response_text = await agent.handle_message(user_message)
            context = agent.get_session_context()

            await websocket.send_json({
                "type": "response",
                "content": response_text,
                "entities": context.get("entities", {}),
            })

    except WebSocketDisconnect:
        logger.info("ws_disconnected", session_id=session_id)
    except Exception as exc:
        logger.error("ws_error", session_id=session_id, error=str(exc))
        await websocket.close(code=1011)
