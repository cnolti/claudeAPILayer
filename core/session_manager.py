"""Session management with SQLite persistence."""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, select, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from api.models.responses import SessionResponse, SessionStatus, TokenUsage
from config import get_logger, settings

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy base class."""

    pass


class SessionModel(Base):
    """Database model for sessions."""

    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=True)
    claude_session_id = Column(String(100), nullable=True)  # Claude's internal session ID
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String(20), default=SessionStatus.ACTIVE.value)
    working_directory = Column(String(500), default=".")
    allowed_tools = Column(Text, default="Read,Glob,Grep,Edit,Write,Bash")

    # Token usage tracking
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cache_read_tokens = Column(Integer, default=0)
    cache_creation_tokens = Column(Integer, default=0)

    # Message count
    message_count = Column(Integer, default=0)


class MessageModel(Base):
    """Database model for message history."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), index=True)
    role = Column(String(20))  # "user" or "assistant"
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    duration_ms = Column(Integer, default=0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    tools_used = Column(Text, default="")


class SessionManager:
    """
    Manages session lifecycle and persistence.

    Provides CRUD operations for sessions with SQLite backend.
    """

    def __init__(self, database_url: str = settings.database_url):
        self.engine = create_async_engine(database_url, echo=settings.debug)
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init_db(self) -> None:
        """Initialize the database schema."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database_initialized")

    async def create_session(
        self,
        name: Optional[str] = None,
        working_directory: str = ".",
        allowed_tools: Optional[list[str]] = None,
    ) -> SessionResponse:
        """Create a new session."""
        session_id = str(uuid.uuid4())

        tools = allowed_tools or ["Read", "Glob", "Grep", "Edit", "Write", "Bash"]
        tools_str = ",".join(tools)

        session = SessionModel(
            id=session_id,
            name=name,
            working_directory=working_directory,
            allowed_tools=tools_str,
        )

        async with self.async_session() as db:
            db.add(session)
            await db.commit()
            await db.refresh(session)

        logger.info("session_created", session_id=session_id, name=name)

        return self._to_response(session)

    async def get_session(self, session_id: str) -> Optional[SessionResponse]:
        """Get a session by ID."""
        async with self.async_session() as db:
            result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = result.scalar_one_or_none()

            if session:
                # Update last accessed
                session.last_accessed = datetime.utcnow()
                await db.commit()
                return self._to_response(session)

        return None

    async def list_sessions(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[SessionStatus] = None,
    ) -> tuple[list[SessionResponse], int]:
        """List all sessions with optional filtering."""
        async with self.async_session() as db:
            query = select(SessionModel)

            if status:
                query = query.where(SessionModel.status == status.value)

            query = query.order_by(SessionModel.last_accessed.desc())
            query = query.offset(offset).limit(limit)

            result = await db.execute(query)
            sessions = result.scalars().all()

            # Get total count
            count_query = select(SessionModel)
            if status:
                count_query = count_query.where(SessionModel.status == status.value)
            count_result = await db.execute(count_query)
            total = len(count_result.scalars().all())

        return [self._to_response(s) for s in sessions], total

    async def update_session(
        self,
        session_id: str,
        claude_session_id: Optional[str] = None,
        status: Optional[SessionStatus] = None,
        token_usage: Optional[dict[str, int]] = None,
        increment_messages: bool = False,
    ) -> Optional[SessionResponse]:
        """Update a session."""
        async with self.async_session() as db:
            result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = result.scalar_one_or_none()

            if not session:
                return None

            if claude_session_id:
                session.claude_session_id = claude_session_id

            if status:
                session.status = status.value

            if token_usage:
                session.input_tokens += token_usage.get("input_tokens", 0)
                session.output_tokens += token_usage.get("output_tokens", 0)
                session.total_tokens += token_usage.get("total_tokens", 0)
                session.cache_read_tokens += token_usage.get("cache_read_tokens", 0)
                session.cache_creation_tokens += token_usage.get("cache_creation_tokens", 0)

            if increment_messages:
                session.message_count += 1

            session.last_accessed = datetime.utcnow()

            await db.commit()
            await db.refresh(session)

            return self._to_response(session)

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        async with self.async_session() as db:
            result = await db.execute(
                delete(SessionModel).where(SessionModel.id == session_id)
            )
            await db.commit()

            deleted = result.rowcount > 0
            if deleted:
                logger.info("session_deleted", session_id=session_id)

            return deleted

    async def fork_session(
        self,
        session_id: str,
        new_name: Optional[str] = None,
    ) -> Optional[SessionResponse]:
        """Fork an existing session."""
        original = await self.get_session(session_id)
        if not original:
            return None

        forked = await self.create_session(
            name=new_name or f"{original.name or 'session'}_fork",
            working_directory=original.working_directory,
            allowed_tools=original.allowed_tools,
        )

        logger.info("session_forked", original_id=session_id, forked_id=forked.id)
        return forked

    async def cleanup_expired(self, ttl_seconds: int = settings.session_ttl) -> int:
        """Delete sessions older than TTL."""
        cutoff = datetime.utcnow() - timedelta(seconds=ttl_seconds)

        async with self.async_session() as db:
            result = await db.execute(
                delete(SessionModel).where(SessionModel.last_accessed < cutoff)
            )
            await db.commit()

            count = result.rowcount
            if count > 0:
                logger.info("expired_sessions_cleaned", count=count)

            return count

    async def get_claude_session_id(self, session_id: str) -> Optional[str]:
        """Get the Claude-internal session ID for resuming conversations."""
        async with self.async_session() as db:
            result = await db.execute(
                select(SessionModel.claude_session_id).where(SessionModel.id == session_id)
            )
            row = result.scalar_one_or_none()
            return row

    def _to_response(self, session: SessionModel) -> SessionResponse:
        """Convert database model to response model."""
        return SessionResponse(
            id=session.id,
            name=session.name,
            created_at=session.created_at,
            last_accessed=session.last_accessed,
            status=SessionStatus(session.status),
            working_directory=session.working_directory,
            allowed_tools=session.allowed_tools.split(",") if session.allowed_tools else [],
            token_usage=TokenUsage(
                input_tokens=session.input_tokens,
                output_tokens=session.output_tokens,
                total_tokens=session.total_tokens,
                cache_read_tokens=session.cache_read_tokens,
                cache_creation_tokens=session.cache_creation_tokens,
            ),
            message_count=session.message_count,
        )

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        duration_ms: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        tools_used: Optional[list[str]] = None,
    ) -> None:
        """Add a message to the session history."""
        message = MessageModel(
            session_id=session_id,
            role=role,
            content=content,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tools_used=",".join(tools_used) if tools_used else "",
        )

        async with self.async_session() as db:
            db.add(message)
            await db.commit()

    async def get_messages(self, session_id: str) -> list[dict]:
        """Get all messages for a session."""
        async with self.async_session() as db:
            result = await db.execute(
                select(MessageModel)
                .where(MessageModel.session_id == session_id)
                .order_by(MessageModel.created_at.asc())
            )
            messages = result.scalars().all()

            return [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at,
                    "duration_ms": msg.duration_ms,
                    "input_tokens": msg.input_tokens,
                    "output_tokens": msg.output_tokens,
                    "tools_used": msg.tools_used.split(",") if msg.tools_used else [],
                }
                for msg in messages
            ]

    async def get_all_sessions_with_messages(self) -> list[dict]:
        """Get all sessions with their message counts for dashboard."""
        async with self.async_session() as db:
            result = await db.execute(
                select(SessionModel).order_by(SessionModel.last_accessed.desc())
            )
            sessions = result.scalars().all()

            return [
                {
                    "id": s.id,
                    "name": s.name,
                    "created_at": s.created_at,
                    "last_accessed": s.last_accessed,
                    "status": s.status,
                    "message_count": s.message_count,
                    "total_tokens": s.total_tokens,
                    "working_directory": s.working_directory,
                }
                for s in sessions
            ]


# Global session manager instance
session_manager = SessionManager()
