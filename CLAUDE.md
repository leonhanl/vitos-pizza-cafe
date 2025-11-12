# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is Vito's Pizza Cafe - an AI customer service application demonstrating AI security vulnerabilities and their mitigation using Palo Alto Networks AI Runtime Security (AIRS). The application is built with LangGraph for conversation flow, RAG for information retrieval, and a lightweight HTML/JS web interface.

## Development Commands

### Setup and Installation
```bash
# Install uv (recommended for faster package management and uvx tool runner)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Note: uvx is included with uv and required for AMAP-STDIO MCP transport

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Unix/MacOS
# .venv\Scripts\activate   # On Windows

# Install dependencies
pip install -e .

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Running the Application
```bash
# Start the backend API server
./start_backend.sh
# Or manually: uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000
# Or as a Python module: python -m backend

# In a separate terminal, launch the web interface
./start_frontend.sh
# Or manually: python -m http.server 5500 --directory ./frontend

# Stop the servers (they run in background and create .pid files)
./stop_backend.sh
./stop_frontend.sh

# Run integration tests
python tests/test_api_integration.py
```

**Note**: The start scripts run servers in the background and create `.pid` files (backend.pid, frontend.pid) for process management. Logs are stored in the `logs/` directory with timestamps.

**Frontend Configuration for Different Domains**: If your frontend and backend are deployed on different domains, configure the backend API URL using the `BACKEND_API_URL` environment variable:

```bash
# Option 1: Inline with start_frontend.sh
BACKEND_API_URL="https://vitos-api.lianglab.net" ./start_frontend.sh

# Option 2: Inline with restart_frontend.sh
BACKEND_API_URL="https://vitos-api.lianglab.net" ./restart_frontend.sh

# Option 3: Using export for multiple commands
export BACKEND_API_URL="https://vitos-api.lianglab.net"
./start_frontend.sh  # or ./restart_frontend.sh
```

**Notes**:
- Do not include the `/api/v1` suffix - it will be added automatically
- If not set, defaults to `http://localhost:8000`
- Configuration is auto-generated into `frontend/config.js` by `scripts/generate_frontend_config.sh` (called automatically)

### Testing Security Features
```bash
# Test AIRS (Palo Alto Networks AI Runtime Security) integration
python tests/test_prisma_airs.py

# The test file demonstrates input/output safety checks using AIRS API
```

## Architecture Overview

### Core Components
- **Chat Service** (`backend/chat_service.py`): Manages conversation flow with RAG retrieval and React agent execution
- **RAG System** (`backend/knowledge_base.py`): Uses FAISS vector store with OpenAI embeddings for document retrieval
- **Database Integration** (`backend/database.py`): SQLite in-memory database with customer information, accessed via SQLDatabaseToolkit
- **LLM Module** (`backend/llm.py`): Centralized LLM initialization using ChatOpenAI
- **MCP Tools** (`backend/mcp_tools.py`): Integration with Model Context Protocol servers (e.g., AMAP)
- **API Layer** (`backend/api.py`): FastAPI REST endpoints for external tool integration
- **Web Interface** (`frontend/index.html`, `frontend/script.js`): Lightweight HTML/JS chat interface with conversation management

### Key Files

**Backend**:
- `backend/chat_service.py`: Main chat service with conversation management
- `backend/api.py`: FastAPI backend server with REST endpoints
- `backend/llm.py`: LLM initialization and configuration
- `backend/mcp_tools.py`: MCP tool integration
- `backend/knowledge_base.py`: RAG system for document retrieval
- `backend/database.py`: Database integration with SQL tools
- `backend/config.py`: Configuration management and environment setup
- `backend/__main__.py`: Module entry point (enables `python -m backend`)

**Frontend**:
- `frontend/index.html`: Web interface HTML structure
- `frontend/script.js`: Frontend JavaScript for chat functionality
- `frontend/style.css`: Web interface styling

**Testing**:
- `tests/api_client.py`: Python HTTP client for backend API (used for programmatic access and red teaming)
- `tests/unit/`: Unit tests for backend components
- `tests/test_api_integration.py`: API endpoint integration tests
- `tests/test_prisma_airs.py`: AIRS security integration tests
- `tests/test_litellm_health.py`: LiteLLM proxy health check tests

**Data & Configuration**:
- `Vitos-Pizza-Cafe-KB/`: Knowledge base markdown files for RAG
- `customer_db.sql`: SQLite database schema with customer data
- `.env.example`: Environment variable configuration template
- `pyproject.toml`: Python package dependencies and metadata

**Scripts**:
- `start_backend.sh`: Start backend server in background
- `stop_backend.sh`: Stop backend server gracefully
- `start_frontend.sh`: Start frontend server in background
- `stop_frontend.sh`: Stop frontend server gracefully

**Documentation & Diagrams**:
- `README.md`: Main project documentation with test cases
- `CLAUDE.md`: Developer guidance for Claude Code (this file)
- `diagrams/`: Architecture diagrams and Excalidraw files

### Data Flow
1. User input → AIRS security check (optional)
2. Vector similarity search in knowledge base (retrieves top N documents)
3. LLM generation with context and optional database queries
4. Response → AIRS output safety check (optional)

## API Keys Required

Configure these in `.env`:

### Required Keys
- `OPENAI_API_KEY`: For LLM responses, tool execution, and document embeddings in RAG system
- `X_PAN_TOKEN`: For Palo Alto Networks AIRS security API

### Embedding Model Configuration
The RAG system uses OpenAI embeddings for document retrieval. Configure via:
- `EMBEDDING_MODEL`: OpenAI embedding model (default: `text-embedding-3-small`)
  - Options: `text-embedding-3-small`, `text-embedding-3-large`, `text-embedding-ada-002`

**Default Behavior**:
- Embeddings default to OpenAI's official endpoint (`https://api.openai.com/v1`)
- Both `OPENAI_BASE_URL` and `OPENAI_EMBEDDING_BASE_URL` default to OpenAI if not set
- This ensures embeddings work even when using alternative LLM providers

**Separate Embedding Credentials** (optional):
To use different providers for LLM and embeddings:
- `OPENAI_EMBEDDING_API_KEY`: Separate API key for embeddings (defaults to `OPENAI_API_KEY`)
- `OPENAI_EMBEDDING_BASE_URL`: Separate base URL for embeddings (defaults to `https://api.openai.com/v1`, **NOT** to `OPENAI_BASE_URL`)

**Important**: `OPENAI_EMBEDDING_BASE_URL` does NOT cascade to `OPENAI_BASE_URL`. This prevents errors when using LLM providers (like DeepSeek) that don't support OpenAI embedding models.

**Use Case Example**: DeepSeek for LLM + OpenAI for embeddings
```bash
# LLM uses DeepSeek
OPENAI_API_KEY=sk-deepseek-...
OPENAI_BASE_URL="https://api.deepseek.com/v1"
LLM_MODEL=deepseek-chat

# Embeddings use native OpenAI (explicit key, URL defaults to OpenAI)
OPENAI_EMBEDDING_API_KEY=sk-proj-...
EMBEDDING_MODEL=text-embedding-3-small
# OPENAI_EMBEDDING_BASE_URL not needed - defaults to OpenAI
```

### LLM Configuration
The application supports multiple LLM providers via OpenAI-compatible APIs:

**OpenAI** (default):
```bash
OPENAI_API_KEY=your_openai_api_key_here
LLM_MODEL=gpt-5-nano  # or gpt-5, gpt-5-mini
# OPENAI_BASE_URL not needed for OpenAI
```

**DeepSeek**:
```bash
OPENAI_API_KEY=your_deepseek_api_key_here
OPENAI_BASE_URL="https://api.deepseek.com/v1"
LLM_MODEL=deepseek-chat
```

**LiteLLM Proxy** (supports multiple models):
```bash
OPENAI_API_KEY=your_litellm_api_key_here
OPENAI_BASE_URL="http://localhost:4000"
LLM_MODEL=deepseek/deepseek-chat
```

**OpenRouter**:
```bash
OPENAI_API_KEY=your_openrouter_api_key_here
OPENAI_BASE_URL="https://openrouter.ai/api/v1"
LLM_MODEL="openai/gpt-5-mini"
```

**AWS Bedrock**:
```bash
OPENAI_API_KEY=your_bedrock_api_key_here
OPENAI_BASE_URL="https://bedrock-runtime.us-west-2.amazonaws.com/openai/v1"
LLM_MODEL="deepseek.v3-v1:0"
```

### AIRS (AI Runtime Security) Configuration
- `X_PAN_TOKEN`: Authentication token for AIRS API
- `X_PAN_AI_MODEL`: Model name for AIRS (e.g., `gpt-5-mini`)
- `X_PAN_APP_NAME`: Application name for AIRS reporting (default: `'Vitos Pizza Cafe'`)
- `X_PAN_APP_USER`: User identifier for AIRS (default: `'Vitos-Admin'`)
- `X_PAN_INPUT_CHECK_PROFILE_NAME`: AIRS profile for input validation (default: `'Demo-Profile-for-Input'`)
- `X_PAN_OUTPUT_CHECK_PROFILE_NAME`: AIRS profile for output validation (default: `'Demo-Profile-for-Output'`)

### Optional Services

**AMAP MCP Tools** (two transport types supported):
- `AMAP_API_KEY`: API key for AMAP services (shared by both transports)
- `AMAP_SSE_ENABLED`: Set to `true` to enable AMAP-SSE (Server-Sent Events) transport (default: `false`)
- `AMAP_STDIO_ENABLED`: Set to `true` to enable AMAP-STDIO (subprocess via uvx) transport (default: `false`)

**LangSmith Tracing**:
- `LANGSMITH_API_KEY`: For LangSmith tracing and debugging
- `LANGSMITH_TRACING`: Set to `true` to enable tracing, `false` to disable
- `LANGSMITH_ENDPOINT`: LangSmith API endpoint (default: `https://api.smith.langchain.com`)
- `LANGSMITH_PROJECT`: Project name for organizing traces (default: `vitos-pizza-cafe`)

**General**:
- `LOG_LEVEL`: Logging verbosity (default: `INFO`)

See `.env.example` for complete configuration examples.

## Security Testing

The application demonstrates these attack vectors:
- Prompt injection (goal hijacking, system prompt leak)
- PII disclosure
- Data poisoning (malicious URLs, toxic content)
- Excessive agency (database tampering)

Use the test cases in README.md to verify security protections are working.

## API Endpoints

The backend provides RESTful API endpoints for external tool integration:

- `POST /api/v1/chat` - Send chat messages and get responses
- `GET /api/v1/conversations` - List active conversations
- `GET /api/v1/conversations/{id}/history` - Get conversation history
- `DELETE /api/v1/conversations/{id}` - Delete a conversation
- `POST /api/v1/conversations/{id}/clear` - Clear conversation history
- `GET /api/v1/health` - Health check endpoint

### Programmatic API Access

The `tests/api_client.py` module provides a Python client (`VitosApiClient`) for programmatic interaction with the backend API. This is particularly useful for:

- **Red teaming and security testing**: Automated attack scenario testing
- **External tool integration**: Integrate with other security tools and frameworks
- **Batch processing**: Process multiple test cases programmatically
- **Stateless testing**: Use `stateless=True` parameter to test without conversation history

Example usage:
```python
from tests.api_client import VitosApiClient

# Initialize client
with VitosApiClient(base_url="http://localhost:8000") as client:
    # Health check
    if client.health_check():
        # Send a message (stateless mode for red teaming)
        response = client.chat("What's on the menu?", stateless=True)
        print(response)

        # Or with conversation tracking
        response = client.chat("What's your special today?", conversation_id="test-123")

        # Get conversation history
        history = client.get_conversation_history("test-123")

        # Clean up
        client.delete_conversation("test-123")
```

## Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/                    # Unit tests only
python tests/test_api_integration.py  # API integration tests
python tests/test_prisma_airs.py      # AIRS security tests
python tests/test_litellm_health.py   # LiteLLM proxy health tests

```

## Development Notes

### Runtime Behavior
- The vector store index is cached in `Vitos-Pizza-Cafe-KB/faiss_index/`
- Database runs in-memory and is recreated on each startup
- Backend API runs on http://localhost:8000 by default (configurable in `start_backend.sh`)
- Frontend runs on http://localhost:5500 by default (configurable in `start_frontend.sh`)
- Frontend communicates with backend via HTTP API (backend URL configurable via `BACKEND_API_URL` env var)
- Frontend configuration is auto-generated at startup into `frontend/config.js` (gitignored)
- MCP tools support multiple transport types:
  - AMAP-SSE: HTTP-based streaming (requires `AMAP_SSE_ENABLED=true` and `AMAP_API_KEY`)
  - AMAP-STDIO: Local subprocess via uvx (requires `AMAP_STDIO_ENABLED=true`, `AMAP_API_KEY`, and uvx installed)
  - Both transports share the same API key and can be enabled simultaneously to demonstrate different MCP transport methods
- LiteLLM proxy server can be used as an alternative LLM backend (see `litellm/` directory and `.env.example`)

### Process Management
- Start scripts (`start_backend.sh`, `start_frontend.sh`) run servers in the background
- Process IDs are stored in `.pid` files (`backend.pid`, `frontend.pid`) in the project root
- Use stop scripts (`stop_backend.sh`, `stop_frontend.sh`) to gracefully shut down servers
- PID files are automatically cleaned up on server shutdown

### Logging and Debugging
- Server logs are stored in the `logs/` directory with timestamp-based filenames
- Log format: `backend-YYYY-MM-DD_HH-MM-SS.log` and `frontend-YYYY-MM-DD_HH-MM-SS.log`
- Log level can be configured via `LOG_LEVEL` environment variable (default: INFO)
- **Tool call logging**: All tool invocations (MCP and database tools) are automatically logged at INFO level with full request/response details, including:
  - Tool name and input parameters when execution starts
  - Complete output response when execution completes
  - Error details if tool execution fails
- Enable LangSmith tracing for detailed conversation flow debugging

### Project Directories
- `logs/`: Timestamped server log files (created by start scripts)
- `temp/`: Temporary files and test artifacts
- `diagrams/`: Architecture diagrams and Excalidraw files
- `Vitos-Pizza-Cafe-KB/faiss_index/`: Cached vector store index files

### LiteLLM Proxy Server (Optional)

The `litellm/` directory contains a complete LiteLLM proxy server setup with Docker Compose:

**Components**:
- **LiteLLM Proxy**: Unified API gateway for multiple LLM providers
- **PostgreSQL Database**: Stores conversation logs and configuration
- **Built-in Guardrails**: Optional AIRS integration at the proxy level

**Configuration Files**:
- `litellm/docker-compose.yml`: Docker services for LiteLLM proxy and PostgreSQL
- `litellm/litellm_config.yaml`: Model configurations and AIRS guardrails

**Supported Models** (configured in litellm_config.yaml):
- OpenAI models (gpt-5, gpt-5-mini, gpt-5-nano)
- DeepSeek models (deepseek-chat, deepseek-reasoner)
- Alibaba Qwen models (qwen-max, qwen-plus via DashScope)

**Features**:
- Model aliasing and unified API interface
- Optional AIRS guardrails per model (input/output filtering)
- PostgreSQL-backed conversation logging
- Health monitoring and detailed debug logging

**Usage**:
```bash
# Start LiteLLM proxy with docker-compose
cd litellm
docker-compose up -d

# Configure your application to use the proxy
OPENAI_BASE_URL="http://localhost:4000"
OPENAI_API_KEY=your_litellm_master_key_here
LLM_MODEL=deepseek-chat  # or any model defined in litellm_config.yaml
```

See `.env.example` for complete LiteLLM environment variable configuration.

## Design Principles

### Engineering Level: **Pragmatic Professional**

This project follows a **pragmatic professional** engineering approach - not enterprise-level complexity, but beyond simple scripting. The goal is clean, testable, maintainable code suitable for security research and red teaming tool integration.

### Architecture Principles

#### 1. **Separation of Concerns**
- **Backend (`backend/`)**: Business logic, API endpoints, data processing
- **Frontend (`frontend/`)**: UI layer, user interactions
- **Tests (`tests/`)**: Comprehensive test coverage for backend logic
- **Clear boundaries**: Frontend communicates with backend only via HTTP API

#### 2. **API-First Design**
- **REST API endpoints** for external tool integration (primary requirement for red teaming)
- **Stateless HTTP communication** between frontend and backend
- **Standard HTTP status codes** and JSON request/response formats
- **OpenAPI documentation** auto-generated by FastAPI

#### 3. **Pragmatic Over Perfect**
- **No over-engineering**: Avoided unnecessary abstraction layers (core/service split)
- **Single responsibility**: Each module has a clear, focused purpose
- **Direct approach**: Business logic consolidated in `ChatService` without complex patterns
- **YAGNI principle**: Don't add features until actually needed

#### 4. **Testability First**
- **Mockable dependencies**: External APIs (AWS Bedrock, DeepSeek) can be mocked for testing
- **Unit tests**: Test business logic in isolation
- **Integration tests**: Test API endpoints end-to-end
- **Test structure**: Separate unit and integration test directories

### Code Organization Principles

#### 5. **Module Structure**
```
backend/               # All backend logic
├── api.py            # FastAPI endpoints
├── chat_service.py   # Core chat functionality
├── knowledge_base.py # RAG operations
├── database.py       # Database integration
├── llm.py            # LLM initialization
├── mcp_tools.py      # MCP tool integration
└── config.py         # Configuration management
frontend/             # UI layer (HTML/JS/CSS)
├── index.html        # Main page structure
├── script.js         # Chat functionality
└── style.css         # Styling
tests/                # Testing suite
├── unit/             # Unit tests
├── test_api_integration.py
├── test_prisma_airs.py
└── test_litellm_health.py
```

#### 6. **Dependency Management**
- **Explicit dependencies**: All external libraries in `pyproject.toml`
- **Version pinning**: Specific versions for reproducible builds
- **Minimal dependencies**: Only add what's actually needed
- **Clear imports**: Relative imports within packages, absolute for external
- **Package installation**: Uses `pip install -e .` for editable installation

#### 7. **Error Handling Strategy**
- **Graceful degradation**: System continues functioning when possible
- **User-friendly messages**: Technical errors translated for end users
- **Comprehensive logging**: Detailed logs for debugging without exposing internals
- **HTTP error codes**: Proper status codes for API responses

### Development Workflow Principles

#### 8. **Testing Strategy**
- **Test pyramid**: More unit tests, fewer integration tests
- **Mock external dependencies**: Tests run without API keys
- **Fast feedback**: Unit tests complete quickly
- **Realistic integration tests**: API tests use actual FastAPI test client

#### 9. **Documentation Approach**
- **Code as documentation**: Clear naming and structure over extensive comments
- **API documentation**: Auto-generated from code (FastAPI/OpenAPI)
- **Usage examples**: Practical examples in CLAUDE.md
- **Architecture decisions**: Document the "why" not just the "what"

### Security Principles (for AI Security Research)

#### 10. **Red Team Integration Ready**
- **HTTP API access**: External tools can programmatically interact
- **Conversation isolation**: Each test can use separate conversation contexts
- **Stateless design**: Tests don't interfere with each other
- **Comprehensive endpoints**: Full CRUD operations on conversations

#### 11. **Defensive Coding**
- **Input validation**: Pydantic models validate all API inputs
- **Error boundaries**: Failures contained and logged appropriately
- **Resource limits**: Conversation history trimmed to prevent memory issues
- **Safe defaults**: Secure configuration as the default

### Quality Standards

#### 12. **Code Quality Metrics**
- **Test coverage**: Aim for >80% coverage on backend logic
- **Type hints**: Use Python type hints for better IDE support and catching errors
- **Linting**: Follow Python best practices (can be enforced with tools like ruff)
- **Documentation**: Every public function/class has docstrings

#### 13. **Performance Considerations**
- **Caching**: Vector store index cached, database tools cached with `@lru_cache`
- **Async where beneficial**: FastAPI endpoints are async-ready
- **Memory management**: Conversation history limits prevent unbounded growth
- **Connection pooling**: HTTP client reuse for frontend-backend communication

### Research Project Principles

#### 14. **Iteration Speed Over Perfection**
- **Rapid prototyping**: Quick implementation and testing of security scenarios
- **Flexible architecture**: Easy to modify for new attack vectors or defenses
- **Minimal ceremony**: No unnecessary processes that slow down research
- **Focus on results**: Code quality serves research goals, not vice versa

#### 15. **Reproducibility**
- **Deterministic testing**: Consistent results across different environments
- **Clear setup instructions**: Anyone can reproduce the research environment
- **Version control**: All changes tracked for experiment reproducibility
- **Isolated environments**: Tests don't depend on external state

### When to Upgrade Engineering Level

**Stay at current level if:**
- Project remains primarily for security research/demos
- Team size stays small (1-3 developers)
- Features focus on AI safety and security testing

**Upgrade to enterprise level if:**
- Multiple production deployments needed
- User authentication/authorization required
- Multi-tenant architecture needed
- Team size grows beyond 5 developers

*This design philosophy prioritizes getting security research done effectively while maintaining professional code quality standards.*