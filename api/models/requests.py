"""Request models for the API."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for chat endpoints."""

    prompt: str = Field(..., min_length=1, description="The prompt to send to Claude")
    session_id: Optional[str] = Field(None, description="Session ID to continue conversation")
    allowed_tools: list[str] = Field(
        default=["Read", "Glob", "Grep"],
        description="List of tools Claude is allowed to use",
    )
    max_turns: Optional[int] = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of agent turns",
    )
    system_prompt: Optional[str] = Field(None, description="Custom system prompt to append")
    working_directory: Optional[str] = Field(None, description="Working directory for operations")
    model: Optional[str] = Field(None, description="Model to use (e.g. 'sonnet', 'opus', 'haiku')")


class StreamChatRequest(ChatRequest):
    """Request model for streaming chat."""

    include_partial: bool = Field(
        default=False,
        description="Include partial/intermediate messages in stream",
    )


class SessionCreateRequest(BaseModel):
    """Request model for creating a new session."""

    name: Optional[str] = Field(None, max_length=100, description="Optional session name")
    working_directory: Optional[str] = Field(".", description="Working directory for the session")
    allowed_tools: list[str] = Field(
        default=["Read", "Glob", "Grep", "Edit", "Write", "Bash"],
        description="Default allowed tools for this session",
    )


class SessionForkRequest(BaseModel):
    """Request model for forking a session."""

    new_name: Optional[str] = Field(None, description="Name for the forked session")


class EvolveRequest(BaseModel):
    """Request model for code evolution."""

    target_path: str = Field(..., description="Path to file or directory to evolve")
    objective: str = Field(..., min_length=10, description="Evolution objective/goal")
    constraints: list[str] = Field(default_factory=list, description="Constraints to respect")
    test_command: Optional[str] = Field(None, description="Command to run tests")
    max_iterations: int = Field(default=5, ge=1, le=20, description="Maximum evolution iterations")
    auto_commit: bool = Field(default=False, description="Automatically commit each iteration")
    branch_name: Optional[str] = Field(None, description="Git branch for evolution")


class FileReadRequest(BaseModel):
    """Request model for reading files."""

    paths: list[str] = Field(..., min_length=1, description="Paths to read")
    include_line_numbers: bool = Field(default=True, description="Include line numbers")


class FileWriteRequest(BaseModel):
    """Request model for writing files."""

    path: str = Field(..., description="Path to write")
    content: str = Field(..., description="Content to write")
    create_dirs: bool = Field(default=True, description="Create parent directories if needed")


class FileSearchRequest(BaseModel):
    """Request model for searching files."""

    pattern: str = Field(..., description="Search pattern (regex)")
    path: str = Field(default=".", description="Directory to search in")
    file_pattern: Optional[str] = Field(None, description="Glob pattern to filter files")
    max_results: int = Field(default=100, ge=1, le=1000, description="Maximum results")


class GitBranchRequest(BaseModel):
    """Request model for creating a git branch."""

    name: str = Field(..., min_length=1, description="Branch name")
    from_branch: Optional[str] = Field(None, description="Branch to create from")


class GitCommitRequest(BaseModel):
    """Request model for creating a commit."""

    message: str = Field(..., min_length=1, description="Commit message")
    paths: list[str] = Field(default_factory=lambda: ["."], description="Paths to commit")


class GitRollbackRequest(BaseModel):
    """Request model for rolling back changes."""

    target: str = Field(..., description="Commit hash or reference to rollback to")
    hard: bool = Field(default=False, description="Hard reset (discard changes)")
