# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is Vito's Pizza Cafe - an AI customer service application demonstrating AI security vulnerabilities and their mitigation using Palo Alto Networks AI Runtime Security (AIRS). The application is built with LangGraph for conversation flow, RAG for information retrieval, and a lightweight HTML/JS web interface.

## Development Commands

### Setup and Installation
```bash
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

# In a separate terminal, launch the web interface
./start_frontend.sh
# Or manually: python -m http.server 5500 --directory ./frontend

# Run integration tests
pytest tests/test_api_integration.py
```

### Testing Security Features
```bash
# Test AIRS (Palo Alto Networks AI Runtime Security) integration
pytest tests/test_prisma_airs.py

# The test file demonstrates input/output safety checks using AIRS API
```

## Architecture Overview

### Core Components
- **Chat Service** (`backend/chat_service.py`): Manages conversation flow with RAG retrieval and React agent execution
- **RAG System** (`backend/knowledge_base.py`): Uses FAISS vector store with Cohere embeddings for document retrieval
- **Database Integration** (`backend/database.py`): SQLite in-memory database with customer information, accessed via SQLDatabaseToolkit
- **LLM Module** (`backend/llm.py`): Centralized LLM initialization using ChatOpenAI
- **MCP Tools** (`backend/mcp_tools.py`): Integration with Model Context Protocol servers (e.g., AMAP)
- **API Layer** (`backend/api.py`): FastAPI REST endpoints for external tool integration
- **Web Interface** (`frontend/index.html`, `frontend/script.js`): Lightweight HTML/JS chat interface with conversation management

### Key Files
- `backend/chat_service.py`: Main chat service with conversation management
- `backend/api.py`: FastAPI backend server with REST endpoints
- `backend/llm.py`: LLM initialization and configuration
- `backend/mcp_tools.py`: MCP tool integration
- `backend/knowledge_base.py`: RAG system for document retrieval
- `backend/database.py`: Database integration with SQL tools
- `backend/config.py`: Configuration management and environment setup
- `frontend/index.html`: Web interface HTML structure
- `frontend/script.js`: Frontend JavaScript for chat functionality
- `tests/`: Test suite including unit and integration tests
- `Vitos-Pizza-Cafe-KB/`: Knowledge base markdown files for RAG
- `customer_db.sql`: SQLite database schema with customer data

### Data Flow
1. User input → AIRS security check (optional)
2. Vector similarity search in knowledge base (retrieves top N documents)
3. LLM generation with context and optional database queries
4. Response → AIRS output safety check (optional)

## API Keys Required

Configure these in `.env`:
- `COHERE_API_KEY`: For embeddings only
- `OPENAI_API_KEY`: For LLM responses and tool execution (supports OpenAI, DeepSeek API, or LiteLLM proxy)
- `OPENAI_BASE_URL`: Optional, for using DeepSeek or LiteLLM proxy (omit for OpenAI)
- `X_PAN_TOKEN`: For AIRS security API
- `AMAP_API_KEY`: Optional, for AMAP MCP tools integration
- `LANGSMITH_API_KEY`: Optional for tracing

See `.env.example` for detailed configuration examples including LiteLLM proxy setup.

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

## Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/                    # Unit tests only
pytest tests/test_api_integration.py  # API integration tests
pytest tests/test_prisma_airs.py      # AIRS security tests
pytest tests/test_litellm_health.py   # LiteLLM proxy health tests

# Run with coverage
pytest --cov=backend tests/

# Run specific test file with verbose output
pytest -v tests/test_api_integration.py
```

## Development Notes

- The vector store index is cached in `Vitos-Pizza-Cafe-KB/faiss_index/`
- Database runs in-memory and is recreated on each startup
- Backend API runs on http://localhost:8000 by default (configurable in `start_backend.sh`)
- Frontend runs on http://localhost:5500 by default (configurable in `start_frontend.sh`)
- Frontend communicates with backend via HTTP API
- MCP tools (like AMAP) are automatically loaded if API keys are configured
- LiteLLM proxy server can be used as an alternative LLM backend (see `litellm/` directory and `.env.example`)

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
- **Mockable dependencies**: External APIs (Cohere, DeepSeek) can be mocked for testing
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