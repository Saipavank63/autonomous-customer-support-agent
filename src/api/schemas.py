from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(default="default", max_length=100)


class ChatResponse(BaseModel):
    response: str
    session_id: str
    entities: Dict = Field(default_factory=dict)
    guardrail_flags: List[str] = Field(default_factory=list)


class SessionInfo(BaseModel):
    session_id: str
    message_count: int
    entities: Dict


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime


class WebSocketMessage(BaseModel):
    type: str = "message"
    content: str
    session_id: str = "default"
