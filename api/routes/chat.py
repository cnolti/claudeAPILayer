"""Chat endpoints for Claude interactions."""

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from api.middleware.auth import verify_api_key
from api.models import ChatRequest, ChatResponse, StreamChatRequest, StreamMessage, TokenUsage
from core.claude_client import claude_client
from core.session_manager import session_manager

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    _: str = Depends(verify_api_key),
) -> ChatResponse:
    """
    Send a message to Claude and get a complete response.

    If session_id is provided, continues the conversation.
    Otherwise, creates a new stateless interaction.
    """
    # Get Claude session ID if resuming
    claude_session_id = None
    if request.session_id:
        session = await session_manager.get_session(request.session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {request.session_id} not found",
            )
        claude_session_id = await session_manager.get_claude_session_id(request.session_id)

    try:
        response = await claude_client.query(
            prompt=request.prompt,
            session_id=claude_session_id,
            allowed_tools=request.allowed_tools,
            max_turns=request.max_turns,
            system_prompt=request.system_prompt,
            working_directory=request.working_directory,
            model=request.model,
        )
    except TimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # Update session and save messages if session provided
    if request.session_id:
        await session_manager.update_session(
            session_id=request.session_id,
            claude_session_id=response.session_id,
            token_usage=response.token_usage,
            increment_messages=True,
        )
        # Save user message
        await session_manager.add_message(
            session_id=request.session_id,
            role="user",
            content=request.prompt,
        )
        # Save assistant response
        await session_manager.add_message(
            session_id=request.session_id,
            role="assistant",
            content=response.result,
            duration_ms=response.duration_ms,
            input_tokens=response.token_usage.get("input_tokens", 0),
            output_tokens=response.token_usage.get("output_tokens", 0),
            tools_used=response.tools_used,
        )

    return ChatResponse(
        result=response.result,
        session_id=response.session_id,
        token_usage=TokenUsage(**response.token_usage),
        duration_ms=response.duration_ms,
        tools_used=response.tools_used,
    )


@router.post("/stream")
async def chat_stream(
    request: StreamChatRequest,
    _: str = Depends(verify_api_key),
) -> StreamingResponse:
    """
    Send a message to Claude and stream the response.

    Returns a stream of newline-delimited JSON objects.
    """
    # Get Claude session ID if resuming
    claude_session_id = None
    if request.session_id:
        session = await session_manager.get_session(request.session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {request.session_id} not found",
            )
        claude_session_id = await session_manager.get_claude_session_id(request.session_id)

    async def generate():
        """Generate streaming response."""
        final_session_id = None

        try:
            async for chunk in claude_client.query_stream(
                prompt=request.prompt,
                session_id=claude_session_id,
                allowed_tools=request.allowed_tools,
                max_turns=request.max_turns,
                system_prompt=request.system_prompt,
                working_directory=request.working_directory,
                include_partial=request.include_partial,
                model=request.model,
            ):
                if chunk.session_id:
                    final_session_id = chunk.session_id

                message = StreamMessage(
                    type=chunk.type,
                    content=chunk.content,
                    timestamp=datetime.utcnow(),
                )
                yield message.model_dump_json() + "\n"

        except Exception as e:
            error_message = StreamMessage(
                type="error",
                content=str(e),
                timestamp=datetime.utcnow(),
            )
            yield error_message.model_dump_json() + "\n"

        # Update session if provided
        if request.session_id and final_session_id:
            await session_manager.update_session(
                session_id=request.session_id,
                claude_session_id=final_session_id,
                increment_messages=True,
            )

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
    )


@router.post("/sessions/{session_id}/message", response_model=ChatResponse)
async def send_message(
    session_id: str,
    request: ChatRequest,
    _: str = Depends(verify_api_key),
) -> ChatResponse:
    """
    Send a message within an existing session.

    This is a convenience endpoint that automatically uses the session's settings.
    """
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    # Use session's tools if not specified in request
    allowed_tools = request.allowed_tools or session.allowed_tools
    working_dir = request.working_directory or session.working_directory

    claude_session_id = await session_manager.get_claude_session_id(session_id)

    try:
        response = await claude_client.query(
            prompt=request.prompt,
            session_id=claude_session_id,
            allowed_tools=allowed_tools,
            max_turns=request.max_turns,
            system_prompt=request.system_prompt,
            working_directory=working_dir,
            model=request.model,
        )
    except TimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # Update session
    await session_manager.update_session(
        session_id=session_id,
        claude_session_id=response.session_id,
        token_usage=response.token_usage,
        increment_messages=True,
    )

    return ChatResponse(
        result=response.result,
        session_id=response.session_id,
        token_usage=TokenUsage(**response.token_usage),
        duration_ms=response.duration_ms,
        tools_used=response.tools_used,
    )
