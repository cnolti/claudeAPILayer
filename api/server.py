"""FastAPI application entry point."""

import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from api.middleware import LoggingMiddleware
from api.models import ErrorResponse, HealthResponse
from api.routes import chat_router, evolve_router, sessions_router
from config import get_logger, settings, setup_logging
from core.session_manager import session_manager

# Setup templates
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Initialize logging
setup_logging()
logger = get_logger(__name__)

# Track startup time
startup_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("application_starting", host=settings.api_host, port=settings.api_port)

    # Initialize database
    await session_manager.init_db()

    logger.info("application_started")

    yield

    # Shutdown
    logger.info("application_shutting_down")


# Create FastAPI app
app = FastAPI(
    title="Claude API Layer",
    description="REST API Layer for Claude CLI - Enables programmatic access for self-evolving code systems",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions."""
    logger.exception("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal Server Error",
            detail=str(exc) if settings.debug else None,
            code="INTERNAL_ERROR",
        ).model_dump(),
    )


# Health check endpoint (no auth required)
@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        uptime_seconds=time.time() - startup_time,
    )


# Web Dashboard - Root endpoint
@app.get("/", response_class=HTMLResponse, tags=["web"])
async def dashboard(request: Request):
    """Web dashboard showing all sessions."""
    sessions = await session_manager.get_all_sessions_with_messages()

    total_messages = sum(s["message_count"] for s in sessions)
    total_tokens = sum(s["total_tokens"] for s in sessions)
    active_sessions = sum(1 for s in sessions if s["status"] == "active")

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "sessions": sessions,
            "total_messages": total_messages,
            "total_tokens": total_tokens,
            "active_sessions": active_sessions,
        },
    )


# Session detail page
@app.get("/sessions/{session_id}", response_class=HTMLResponse, tags=["web"])
async def session_detail(request: Request, session_id: str):
    """Web page showing session details and message history."""
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = await session_manager.get_messages(session_id)

    return templates.TemplateResponse(
        "session_detail.html",
        {
            "request": request,
            "session": session,
            "messages": messages,
        },
    )


# API info endpoint (JSON)
@app.get("/api", tags=["system"])
async def api_info() -> dict:
    """API information endpoint."""
    return {
        "name": "Claude API Layer",
        "version": "0.1.0",
        "docs": "/docs" if settings.debug else "Disabled in production",
        "health": "/health",
    }


# Include routers
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(evolve_router, prefix="/api/v1")


def main():
    """Run the application."""
    import uvicorn

    uvicorn.run(
        "api.server:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
