# Claude API Layer

REST API wrapper for the Claude CLI, enabling programmatic access for self-evolving code systems and other automation tools.

## Features

- **REST API** - HTTP endpoints for Claude interactions
- **Session Management** - Persistent conversations with SQLite storage
- **Message History** - Full conversation tracking per session
- **Web Dashboard** - Visual interface for monitoring sessions
- **Model Selection** - Per-request model choice with fallback support
- **File Operations** - Claude can read/write files in specified directories
- **Code Evolution** - Endpoints for iterative code improvement workflows

## Quick Start

### Prerequisites

- Python 3.11+
- [Claude CLI](https://claude.ai/code) installed and authenticated

### Installation

```bash
git clone https://github.com/cnolti/claudeAPILayer.git
cd claudeAPILayer

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### Run

```bash
python -m api.server
```

Server starts at **http://localhost:8000**

## Configuration

Create a `.env` file:

```env
# API Settings
API_HOST=0.0.0.0
API_PORT=8000
API_KEY=your-secret-key
DEBUG=true

# Claude Settings
CLAUDE_MODEL=sonnet
CLAUDE_FALLBACK_MODEL=haiku
CLAUDE_TIMEOUT=300

# Database
DATABASE_URL=sqlite+aiosqlite:///./data/sessions.db
```

## API Endpoints

### Chat

```bash
# Simple chat
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello!", "allowed_tools": []}'

# Chat with specific model
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Complex task", "model": "opus", "allowed_tools": ["Read", "Edit"]}'
```

### Sessions

```bash
# Create session with working directory
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Project",
    "working_directory": "/path/to/project",
    "allowed_tools": ["Read", "Glob", "Grep", "Edit", "Write", "Bash"]
  }'

# Continue conversation in session
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Refactor the main.py", "session_id": "uuid-here"}'

# List sessions
curl http://localhost:8000/api/v1/sessions \
  -H "X-API-Key: your-api-key"
```

### Code Evolution

```bash
# Start evolution task
curl -X POST http://localhost:8000/api/v1/evolve/iterate \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "target_path": "./src/algorithm.py",
    "objective": "Optimize performance",
    "test_command": "pytest tests/",
    "max_iterations": 5
  }'

# Check status
curl http://localhost:8000/api/v1/evolve/status/{task_id} \
  -H "X-API-Key: your-api-key"
```

## Web Dashboard

Open **http://localhost:8000** in your browser to access the dashboard:

- View all sessions
- See message history
- Monitor token usage
- Send messages directly

## Available Tools

When creating sessions or sending requests, you can specify which tools Claude can use:

| Tool | Description |
|------|-------------|
| `Read` | Read file contents |
| `Glob` | Search files by pattern |
| `Grep` | Search file contents |
| `Edit` | Modify existing files |
| `Write` | Create new files |
| `Bash` | Execute shell commands |

## Model Aliases

| Alias | Model |
|-------|-------|
| `opus` | claude-opus-4-5-20251101 |
| `sonnet` | claude-sonnet-4-20250514 |
| `haiku` | claude-haiku-4-5-20251001 |

## Project Structure

```
claude-api-layer/
├── api/
│   ├── server.py          # FastAPI application
│   ├── routes/            # API endpoints
│   ├── models/            # Pydantic schemas
│   └── middleware/        # Auth & logging
├── core/
│   ├── claude_client.py   # Claude CLI wrapper
│   └── session_manager.py # SQLite persistence
├── templates/             # Jinja2 web templates
├── docker/                # Docker configuration
└── examples/              # Usage examples
```

## Docker

```bash
cd docker
docker-compose up -d
```

## Use Cases

- **Self-Evolving Code** - Automated code improvement pipelines
- **CI/CD Integration** - Claude-powered code review and fixes
- **Development Tools** - IDE plugins and automation scripts
- **Batch Processing** - Process multiple files with Claude

## License

MIT
