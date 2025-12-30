"""Claude CLI client wrapper for programmatic access."""

import asyncio
import json
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from config import get_logger, settings

logger = get_logger(__name__)


@dataclass
class ClaudeResponse:
    """Response from Claude CLI."""

    result: str
    session_id: str
    token_usage: dict[str, int] = field(default_factory=dict)
    duration_ms: int = 0
    tools_used: list[str] = field(default_factory=list)
    raw_output: Optional[dict[str, Any]] = None


@dataclass
class StreamChunk:
    """Chunk from streaming response."""

    type: str  # "text", "tool_use", "tool_result", "error", "done"
    content: Any
    session_id: Optional[str] = None


class ClaudeClient:
    """
    Client for interacting with Claude CLI programmatically.

    Uses the Claude CLI in print mode (-p) with JSON output for structured responses.
    Supports both synchronous and streaming interactions.
    """

    def __init__(
        self,
        binary: str = settings.claude_binary,
        default_model: str = settings.claude_model,
        fallback_model: str = settings.claude_fallback_model,
        timeout: int = settings.claude_timeout,
    ):
        self.binary = binary
        self.default_model = default_model
        self.fallback_model = fallback_model
        self.timeout = timeout

    def _build_command(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        allowed_tools: Optional[list[str]] = None,
        max_turns: Optional[int] = None,
        system_prompt: Optional[str] = None,
        working_directory: Optional[str] = None,
        output_format: str = "json",
        model: Optional[str] = None,
    ) -> list[str]:
        """Build the Claude CLI command."""
        cmd = [self.binary, "-p", prompt]

        # Output format
        cmd.extend(["--output-format", output_format])

        # Session management
        if session_id:
            cmd.extend(["--resume", session_id])

        # Tool permissions
        if allowed_tools:
            cmd.extend(["--allowedTools", ",".join(allowed_tools)])

        # System prompt
        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])

        # Model selection (request model > default model)
        selected_model = model or self.default_model
        if selected_model:
            cmd.extend(["--model", selected_model])

        # Fallback model
        if self.fallback_model:
            cmd.extend(["--fallback-model", self.fallback_model])

        return cmd

    async def query(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        allowed_tools: Optional[list[str]] = None,
        max_turns: Optional[int] = None,
        system_prompt: Optional[str] = None,
        working_directory: Optional[str] = None,
        model: Optional[str] = None,
    ) -> ClaudeResponse:
        """
        Send a query to Claude and wait for the complete response.

        Args:
            prompt: The prompt to send
            session_id: Optional session ID to continue a conversation
            allowed_tools: List of tools Claude is allowed to use
            max_turns: Maximum number of agent turns
            system_prompt: Custom system prompt to append
            working_directory: Working directory for file operations
            model: Model to use (overrides default)

        Returns:
            ClaudeResponse with the result
        """
        cmd = self._build_command(
            prompt=prompt,
            session_id=session_id,
            allowed_tools=allowed_tools,
            max_turns=max_turns,
            system_prompt=system_prompt,
            working_directory=working_directory,
            output_format="json",
            model=model,
        )

        logger.info("executing_claude_query", command=cmd[0], prompt_length=len(prompt))
        start_time = time.time()

        try:
            # Run in executor to not block
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_directory,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error("claude_query_failed", error=error_msg, returncode=process.returncode)
                raise RuntimeError(f"Claude CLI failed: {error_msg}")

            # Parse JSON response
            output = stdout.decode()
            try:
                data = json.loads(output)
            except json.JSONDecodeError:
                # If not valid JSON, treat as plain text
                return ClaudeResponse(
                    result=output,
                    session_id=session_id or "",
                    duration_ms=duration_ms,
                )

            # Extract response data
            result = data.get("result", "")
            new_session_id = data.get("session_id", session_id or "")

            # Extract token usage from usage field
            token_usage = {}
            if "usage" in data:
                usage = data["usage"]
                token_usage = {
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                    "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                    "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
                    "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
                }

            # Cost tracking
            cost_usd = data.get("total_cost_usd", 0)

            # Tools used would need to be tracked differently
            tools_used = []

            logger.info(
                "claude_query_complete",
                session_id=new_session_id,
                duration_ms=duration_ms,
                tools_used=tools_used,
            )

            return ClaudeResponse(
                result=result,
                session_id=new_session_id,
                token_usage=token_usage,
                duration_ms=duration_ms,
                tools_used=tools_used,
                raw_output=data,
            )

        except asyncio.TimeoutError:
            logger.error("claude_query_timeout", timeout=self.timeout)
            raise TimeoutError(f"Claude query timed out after {self.timeout}s")

    async def query_stream(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        allowed_tools: Optional[list[str]] = None,
        max_turns: Optional[int] = None,
        system_prompt: Optional[str] = None,
        working_directory: Optional[str] = None,
        include_partial: bool = False,
        model: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Send a query to Claude and stream the response.

        Yields StreamChunk objects as they arrive.
        """
        cmd = self._build_command(
            prompt=prompt,
            session_id=session_id,
            allowed_tools=allowed_tools,
            max_turns=max_turns,
            system_prompt=system_prompt,
            working_directory=working_directory,
            output_format="stream-json",
            model=model,
        )

        if include_partial:
            cmd.append("--include-partial-messages")

        logger.info("starting_claude_stream", prompt_length=len(prompt))

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_directory,
        )

        captured_session_id = session_id

        try:
            while True:
                line = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=self.timeout,
                )

                if not line:
                    break

                line_str = line.decode().strip()
                if not line_str:
                    continue

                try:
                    data = json.loads(line_str)

                    # Handle different message types
                    msg_type = data.get("type", "unknown")

                    if msg_type == "init":
                        captured_session_id = data.get("session_id", captured_session_id)
                        continue

                    if msg_type == "text":
                        yield StreamChunk(
                            type="text",
                            content=data.get("content", ""),
                            session_id=captured_session_id,
                        )
                    elif msg_type == "tool_use":
                        yield StreamChunk(
                            type="tool_use",
                            content={
                                "name": data.get("name"),
                                "input": data.get("input"),
                            },
                            session_id=captured_session_id,
                        )
                    elif msg_type == "tool_result":
                        yield StreamChunk(
                            type="tool_result",
                            content=data.get("content"),
                            session_id=captured_session_id,
                        )
                    elif msg_type == "result":
                        yield StreamChunk(
                            type="done",
                            content=data.get("result", ""),
                            session_id=captured_session_id,
                        )

                except json.JSONDecodeError:
                    # Non-JSON line, yield as text
                    yield StreamChunk(
                        type="text",
                        content=line_str,
                        session_id=captured_session_id,
                    )

        except asyncio.TimeoutError:
            yield StreamChunk(type="error", content="Stream timeout")
        finally:
            if process.returncode is None:
                process.kill()

        yield StreamChunk(type="done", content="", session_id=captured_session_id)

    async def health_check(self) -> bool:
        """Check if Claude CLI is available and working."""
        try:
            process = await asyncio.create_subprocess_exec(
                self.binary,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(process.communicate(), timeout=10)
            return process.returncode == 0
        except Exception as e:
            logger.warning("claude_health_check_failed", error=str(e))
            return False


# Global client instance
claude_client = ClaudeClient()
