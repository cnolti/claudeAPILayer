"""Session management endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.middleware.auth import verify_api_key
from api.models import (
    SessionCreateRequest,
    SessionForkRequest,
    SessionListResponse,
    SessionResponse,
    SessionStatus,
)
from core.session_manager import session_manager

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: SessionCreateRequest,
    _: str = Depends(verify_api_key),
) -> SessionResponse:
    """Create a new session."""
    return await session_manager.create_session(
        name=request.name,
        working_directory=request.working_directory,
        allowed_tools=request.allowed_tools,
    )


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    status_filter: Optional[SessionStatus] = Query(default=None, alias="status"),
    _: str = Depends(verify_api_key),
) -> SessionListResponse:
    """List all sessions."""
    sessions, total = await session_manager.list_sessions(
        limit=limit,
        offset=offset,
        status=status_filter,
    )
    return SessionListResponse(sessions=sessions, total=total)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    _: str = Depends(verify_api_key),
) -> SessionResponse:
    """Get a session by ID."""
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    _: str = Depends(verify_api_key),
) -> None:
    """Delete a session."""
    deleted = await session_manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )


@router.post("/{session_id}/fork", response_model=SessionResponse)
async def fork_session(
    session_id: str,
    request: SessionForkRequest,
    _: str = Depends(verify_api_key),
) -> SessionResponse:
    """Fork an existing session."""
    forked = await session_manager.fork_session(
        session_id=session_id,
        new_name=request.new_name,
    )
    if not forked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return forked
