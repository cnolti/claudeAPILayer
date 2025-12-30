"""Response models for the API."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Session status enumeration."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class TaskStatus(str, Enum):
    """Task status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TokenUsage(BaseModel):
    """Token usage statistics."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


class SessionResponse(BaseModel):
    """Response model for session information."""

    id: str
    name: Optional[str] = None
    created_at: datetime
    last_accessed: datetime
    status: SessionStatus
    working_directory: str
    allowed_tools: list[str]
    token_usage: TokenUsage
    message_count: int = 0


class SessionListResponse(BaseModel):
    """Response model for listing sessions."""

    sessions: list[SessionResponse]
    total: int


class ChatResponse(BaseModel):
    """Response model for chat endpoints."""

    result: str
    session_id: str
    token_usage: TokenUsage
    duration_ms: int
    tools_used: list[str] = Field(default_factory=list)


class StreamMessage(BaseModel):
    """Model for streaming messages."""

    type: str  # "text", "tool_use", "tool_result", "error", "done"
    content: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EvolveResponse(BaseModel):
    """Response model for evolution task creation."""

    task_id: str
    status: TaskStatus
    message: str


class EvolveStatusResponse(BaseModel):
    """Response model for evolution status."""

    task_id: str
    status: TaskStatus
    current_iteration: int
    max_iterations: int
    objective: str
    changes: list[dict[str, Any]] = Field(default_factory=list)
    test_results: list[dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class FileContent(BaseModel):
    """Model for file content."""

    path: str
    content: str
    size: int
    modified_at: datetime


class FileReadResponse(BaseModel):
    """Response model for file read operations."""

    files: list[FileContent]
    errors: list[dict[str, str]] = Field(default_factory=list)


class FileWriteResponse(BaseModel):
    """Response model for file write operations."""

    path: str
    success: bool
    message: str


class SearchMatch(BaseModel):
    """Model for search match."""

    path: str
    line_number: int
    line_content: str
    match_start: int
    match_end: int


class FileSearchResponse(BaseModel):
    """Response model for file search."""

    matches: list[SearchMatch]
    total_matches: int
    files_searched: int


class GitBranchResponse(BaseModel):
    """Response model for git branch operations."""

    name: str
    created: bool
    message: str


class GitCommitResponse(BaseModel):
    """Response model for git commit operations."""

    commit_hash: str
    message: str
    files_changed: int


class GitHistoryEntry(BaseModel):
    """Model for git history entry."""

    hash: str
    short_hash: str
    message: str
    author: str
    date: datetime
    files_changed: list[str]


class GitHistoryResponse(BaseModel):
    """Response model for git history."""

    entries: list[GitHistoryEntry]
    total: int


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: Optional[str] = None
    code: str = "UNKNOWN_ERROR"


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str
    uptime_seconds: float
