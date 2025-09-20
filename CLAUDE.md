# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is Vito's Pizza Cafe - an AI customer service application demonstrating AI security vulnerabilities and their mitigation using Palo Alto Networks AI Runtime Security (AIRS). The application is built with LangGraph for conversation flow, RAG for information retrieval, and Streamlit for the web interface.

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
python -m backend.api

# In a separate terminal, launch the web interface
streamlit run src/frontend/app.py

# Or run frontend using module
python -m frontend

# Test the chat service directly (for development)
python -m backend.chat_service

# Run integration tests
python tests/test_vitos_pizza_cafe.py
```

### Testing Security Features
```bash
# Enable AIRS protection by uncommenting lines in vitos_pizza_cafe.py:
# - Line 217: @check_message_safety
# - Lines 283-287: safety_check implementation
```

## Architecture Overview

### Core Components
- **Chat Service** (`src/backend/chat_service.py`): Manages conversation flow with RAG retrieval and React agent execution
- **RAG System** (`src/backend/knowledge_base.py`): Uses FAISS vector store with Cohere embeddings and reranking for document retrieval
- **Database Integration** (`src/backend/database.py`): SQLite in-memory database with customer information, accessed via SQLDatabaseToolkit
- **API Layer** (`src/backend/api.py`): FastAPI REST endpoints for external tool integration
- **Web Interface** (`src/frontend/app.py`): Streamlit-based chat interface with conversation management

### Key Files
- `src/backend/chat_service.py`: Main chat service with conversation management
- `src/backend/api.py`: FastAPI backend server with REST endpoints
- `src/frontend/app.py`: Streamlit web interface
- `src/backend/knowledge_base.py`: RAG system for document retrieval
- `src/backend/database.py`: Database integration with SQL tools
- `tests/backend/`: Comprehensive backend test suite
- `Vitos-Pizza-Cafe-KB/`: Knowledge base markdown files for RAG
- `customer_db.sql`: SQLite database schema with customer data

### Data Flow
1. User input → AIRS security check (optional)
2. Vector similarity search in knowledge base
3. Cohere reranking of retrieved documents
4. LLM generation with context and optional database queries
5. Response → AIRS output safety check (optional)

## API Keys Required

Configure these in `.env`:
- `COHERE_API_KEY`: For embeddings and reranking
- `DEEPSEEK_API_KEY`: For LLM responses and tool execution
- `X_PAN_TOKEN`: For AIRS security API
- `LANGSMITH_API_KEY`: Optional for tracing

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
# Run all backend tests
pytest

# Run specific test categories
pytest tests/backend/unit/          # Unit tests only
pytest tests/backend/integration/   # Integration tests only

# Run with coverage
pytest --cov=backend tests/backend/

# Run specific test file
pytest tests/test_vitos_pizza_cafe.py
```

## Development Notes

- The vector store index is cached in `Vitos-Pizza-Cafe-KB/faiss_index/`
- Database runs in-memory and is recreated on each startup
- Backend API runs on http://localhost:8000 by default
- Frontend communicates with backend via HTTP API
- Security checks can be toggled by commenting/uncommenting decorator lines

## Design Principles

### Engineering Level: **Pragmatic Professional**

This project follows a **pragmatic professional** engineering approach - not enterprise-level complexity, but beyond simple scripting. The goal is clean, testable, maintainable code suitable for security research and red teaming tool integration.

### Architecture Principles

#### 1. **Separation of Concerns**
- **Backend (`src/backend/`)**: Business logic, API endpoints, data processing
- **Frontend (`src/frontend/`)**: UI layer, user interactions
- **Tests (`tests/backend/`)**: Comprehensive test coverage for backend logic
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
src/
├── backend/           # All backend logic
│   ├── api.py        # FastAPI endpoints
│   ├── chat_service.py # Core chat functionality
│   ├── knowledge_base.py # RAG operations
│   ├── database.py   # Database integration
│   └── config.py     # Configuration management
├── frontend/         # UI layer
└── tests/backend/    # Backend-focused testing
```

#### 6. **Dependency Management**
- **Explicit dependencies**: All external libraries in `requirements.txt`
- **Version pinning**: Specific versions for reproducible builds
- **Minimal dependencies**: Only add what's actually needed
- **Clear imports**: Relative imports within packages, absolute for external

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