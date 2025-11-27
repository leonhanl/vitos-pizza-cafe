# Streaming Mode Implementation Plan for Vito's Pizza Cafe

**Status**: Ready for implementation
**Estimated Effort**: 10-14 hours (1.5-2 days)
**Created**: 2025-11-26

---

## Overview

This document provides a complete implementation plan for adding streaming mode to Vito's Pizza Cafe chat application. The current implementation uses blocking `ainvoke()` calls that wait for complete responses before displaying anything to users. Streaming will provide progressive response rendering with real-time tool call visibility.

**Key Benefits**:
- First content appears within 1-2 seconds (vs 5-30s currently)
- Progressive markdown rendering as text is generated
- Real-time visibility into tool execution (database queries, MCP tools)
- Better perceived performance and user experience
- Valuable for AI security demonstrations and red teaming

---

## Current Architecture Assessment

### What We Have ✅
- **LangGraph**: Already supports streaming via `astream()` method
- **FastAPI**: Has `StreamingResponse` for SSE
- **ChatOpenAI**: Supports streaming natively
- **sse-starlette**: Already installed as dependency
- **Frontend**: Uses fetch API which supports streaming

### Key Finding
**No new dependencies required** - all necessary streaming capabilities are already available.

---

## Design Decisions

### ✅ Confirmed Decisions

1. **AIRS Integration**: Not included in this iteration - focus on core streaming functionality
   - Can be added later with buffered streaming approach

2. **API Design**: Separate endpoint `/api/v1/chat/stream` - non-breaking change
   - Keeps existing `/api/v1/chat` endpoint functional
   - Allows gradual migration and testing

3. **UI Approach**: Progressive rendering with real-time tool call visibility
   - Stream text tokens as they're generated
   - Display tool invocations and results in real-time
   - No loading animation - immediate progressive feedback

4. **Tool Display**: Show tool invocations and results in real-time with expandable details
   - **Rationale**: While a typical customer-facing app would hide tool calls for cleaner UX, this is valuable for:
     - **AI security demonstrations**: Shows how agents interact with tools (database, MCP)
     - **Red teaming**: Visibility into what tools are called helps identify security issues
     - **Research & debugging**: Understanding agent reasoning and tool execution flow
     - **Transparency**: Demonstrates AI safety concepts to stakeholders
   - **Note**: In production customer-facing deployment, tool calls could be hidden by filtering out `tool_call` and `tool_result` events in the frontend

---

## Implementation Phases

### Phase 1: Backend Streaming Foundation (3-4 hours)
1. ✅ Add `aprocess_query_stream()` to ChatService
2. ✅ Add `process_stateless_query_stream()` for stateless mode
3. Unit tests for streaming methods
4. Verify LangGraph streaming behavior with manual testing

### Phase 2: Backend API Endpoint (2-3 hours)
1. ✅ Create `/api/v1/chat/stream` endpoint with SSE format
2. ✅ Wire up ChatService streaming method
3. ✅ Handle errors as SSE events
4. Integration tests for streaming endpoint

### Phase 3: Frontend Implementation (3-4 hours)
1. ✅ Implement `sendMessageStream()` function
2. ✅ Add SSE parsing with ReadableStream
3. ✅ Progressive markdown rendering
4. ✅ Error handling and connection management
5. ✅ Add CSS styling for tool calls

### Phase 4: Testing & Polish (2-3 hours)
1. End-to-end streaming tests
2. Edge case testing (connection drops, long responses)
3. Performance validation
4. Update README with streaming endpoint documentation

---

## Critical Files to Modify

### Backend (2 files)

#### 1. `backend/chat_service.py`
**Changes**: Add streaming methods that yield dict events

**Required imports**:
```python
from typing import List, Optional, Dict, Any, AsyncIterator
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
```

**New methods to add**:
- `aprocess_query_stream(self, user_input: str) -> AsyncIterator[Dict[str, Any]]`
- `process_stateless_query_stream(user_input: str) -> AsyncIterator[Dict[str, Any]]` (static method)

**Event types yielded**:
- `{"type": "token", "content": str}` - Text content chunks
- `{"type": "tool_call", "tool": str, "args": dict}` - Tool invocations
- `{"type": "tool_result", "tool_call_id": str, "result": str}` - Tool results
- `{"type": "error", "error": str}` - Errors

#### 2. `backend/api.py`
**Changes**: Add SSE streaming endpoint

**Required imports**:
```python
import json
from fastapi.responses import StreamingResponse
```

**New endpoint to add**:
- `POST /api/v1/chat/stream` - Streaming chat endpoint
- Handles both stateful and stateless modes
- Returns `StreamingResponse` with `text/event-stream` media type
- Sets headers: `Cache-Control`, `Connection`, `X-Accel-Buffering`

### Frontend (2 files)

#### 3. `frontend/script.js`
**Changes**: Add streaming client function

**Modifications**:
1. Update event listeners to call `sendMessageStream()` instead of `sendMessage()`
2. Add new function: `sendMessageStream()`
   - Use `fetch()` with `response.body.getReader()`
   - Parse SSE format (lines starting with `data: `)
   - Handle event types: `start`, `token`, `tool_call`, `tool_result`, `done`, `error`
   - Progressively render markdown with `marked.parse()`
   - Display tool calls with expandable details

#### 4. `frontend/style.css`
**Changes**: Add tool call styling

**New CSS classes**:
- `.tool-call` - Blue background, left border
- `.tool-result` - Green background, left border
- `.tool-call pre`, `.tool-result pre` - Formatted code display
- `.tool-call details summary` - Cursor and hover effects

### Testing (2 files)

#### 5. `tests/test_api_integration.py`
**Changes**: Add streaming tests
- Test SSE format
- Test event types
- Test tool call events

#### 6. `tests/unit/test_chat_service.py`
**Changes**: Add ChatService streaming tests
- Test yielding of different event types

---

## Technical Implementation Details

### SSE Format Examples

**With Tool Calls:**
```
data: {"type": "start", "conversation_id": "abc-123"}

data: {"type": "token", "content": "Let"}

data: {"type": "token", "content": " me"}

data: {"type": "token", "content": " search"}

data: {"type": "tool_call", "tool": "sql_db_query", "args": {"query": "SELECT * FROM customers WHERE name = 'John'"}}

data: {"type": "tool_result", "tool_call_id": "call_123", "result": "Found 1 customer: John Doe"}

data: {"type": "token", "content": "I"}

data: {"type": "token", "content": " found"}

data: {"type": "done"}
```

**Without Tool Calls (simple text response):**
```
data: {"type": "start", "conversation_id": "abc-123"}

data: {"type": "token", "content": "Our"}

data: {"type": "token", "content": " pizza"}

data: {"type": "token", "content": " menu"}

data: {"type": "done"}
```

---

## Backend Implementation

### LangGraph Stream Mode

**Important: Tool Calls ARE Streamed**

LangGraph's `astream()` with `stream_mode="messages"` streams:
- ✅ Agent text responses (token-by-token)
- ✅ Tool invocations (tool name + arguments in AIMessage)
- ✅ Tool results (ToolMessage after execution completes)
- ❌ Tool execution itself (happens synchronously, not streamed)

**Stream Event Flow:**
1. Agent generates AIMessage with `tool_calls` attribute → **streamed**
2. Tool executes (e.g., database query) → **NOT streamed** (blocking)
3. ToolMessage with result added to state → **streamed**
4. Agent continues with final response → **streamed token-by-token**

### ChatService Streaming Method

```python
async def aprocess_query_stream(self, user_input: str) -> AsyncIterator[Dict[str, Any]]:
    """Stream response chunks including tool calls."""
    logger.info(f"Streaming query: {user_input}, Conversation ID: {self.conversation_id}")

    try:
        # 1. Retrieve context (mandatory RAG)
        context = retrieve_context(user_input)

        # 2. Get LLM and tools
        llm = get_llm()
        db_tools = get_database_tools(llm)
        mcp_tools = await get_mcp_tools()
        tools = db_tools + mcp_tools

        # 3. Create React agent
        react_agent = create_react_agent(model=llm, tools=tools)

        # 4. Prepare messages
        system_message = f"{SYSTEM_PROMPT}\n\n{context}"
        messages = [SystemMessage(content=system_message)]
        if self.conversation_history:
            messages.extend(self.conversation_history)
        messages.append(HumanMessage(content=user_input))

        accumulated_response = ""

        # 5. Stream with messages mode
        async for chunk in react_agent.astream(
            {"messages": messages},
            config={"callbacks": [ToolLoggingHandler()]},
            stream_mode="messages"
        ):
            # Chunk format: (namespace, mode, (message, metadata))
            if len(chunk) == 3:
                namespace, mode, data = chunk
                if mode == "messages":
                    message, metadata = data

                    # Handle AIMessage (agent response or tool calls)
                    if isinstance(message, AIMessage):
                        if message.tool_calls:
                            # Tool invocation - yield for UI display
                            for tool_call in message.tool_calls:
                                yield {
                                    "type": "tool_call",
                                    "tool": tool_call["name"],
                                    "args": tool_call["args"]
                                }
                        elif message.content:
                            # Agent text response - yield token
                            content_chunk = message.content
                            accumulated_response += content_chunk
                            yield {
                                "type": "token",
                                "content": content_chunk
                            }

                    # Handle ToolMessage (tool results)
                    elif isinstance(message, ToolMessage):
                        yield {
                            "type": "tool_result",
                            "tool_call_id": message.tool_call_id,
                            "result": message.content
                        }

        # 6. Update conversation history after streaming completes
        self.conversation_history.append(HumanMessage(content=user_input))
        self.conversation_history.append(AIMessage(content=accumulated_response))

    except Exception as e:
        logger.error(f"Error streaming query: {e}")
        yield {
            "type": "error",
            "error": str(e)
        }
```

### API Streaming Endpoint

```python
@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat endpoint with tool call visibility."""
    conversation_id = request.conversation_id or str(uuid4())

    if request.stateless:
        from .chat_service import ChatService

        async def event_stream():
            try:
                yield f"data: {json.dumps({'type': 'start', 'conversation_id': None})}\n\n"

                async for event in ChatService.process_stateless_query_stream(request.message):
                    yield f"data: {json.dumps(event)}\n\n"

                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            except Exception as e:
                logger.error(f"Streaming error: {str(e)}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    # Stateful mode
    chat_service = get_or_create_chat_service(conversation_id)

    async def event_stream():
        try:
            yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation_id})}\n\n"

            async for event in chat_service.aprocess_query_stream(request.message):
                yield f"data: {json.dumps(event)}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Streaming error: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
```

---

## Frontend Implementation

### Streaming Client Function

```javascript
async function sendMessageStream() {
    const message = chatInput.value.trim();
    if (!message) return;

    // Disable input
    chatInput.value = '';
    chatInput.disabled = true;
    sendButton.disabled = true;

    // Add user message
    addMessage(message, 'user');

    // Create assistant message placeholder
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = '<div class="message-content"></div>';
    chatMessages.appendChild(messageDiv);
    const contentDiv = messageDiv.querySelector('.message-content');

    let accumulatedContent = "";
    let toolCallsHtml = "";  // Accumulate tool call displays

    try {
        const response = await fetch(`${API_URL}/chat/stream`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                message: message,
                conversation_id: currentConversationId
            })
        });

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const {done, value} = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, {stream: true});
            const messages = buffer.split('\n\n');
            buffer = messages.pop(); // Keep incomplete message in buffer

            for (const msg of messages) {
                if (msg.startsWith('data: ')) {
                    const data = JSON.parse(msg.substring(6));

                    if (data.type === 'start') {
                        if (data.conversation_id) {
                            currentConversationId = data.conversation_id;
                        }
                    }
                    else if (data.type === 'token') {
                        // Agent text response - accumulate and render
                        accumulatedContent += data.content;
                        const fullHtml = toolCallsHtml + marked.parse(accumulatedContent);
                        contentDiv.innerHTML = fullHtml;
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                    else if (data.type === 'tool_call') {
                        // Tool invocation - show in UI
                        const toolName = data.tool;
                        const toolArgs = JSON.stringify(data.args, null, 2);
                        toolCallsHtml += `
                            <div class="tool-call">
                                <strong>🔧 Calling tool:</strong> ${toolName}
                                <details>
                                    <summary>Arguments</summary>
                                    <pre>${escapeHtml(toolArgs)}</pre>
                                </details>
                            </div>
                        `;
                        contentDiv.innerHTML = toolCallsHtml + marked.parse(accumulatedContent);
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                    else if (data.type === 'tool_result') {
                        // Tool result - show in UI
                        const result = data.result;
                        toolCallsHtml += `
                            <div class="tool-result">
                                <strong>✅ Tool result:</strong>
                                <pre>${escapeHtml(result)}</pre>
                            </div>
                        `;
                        contentDiv.innerHTML = toolCallsHtml + marked.parse(accumulatedContent);
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                    else if (data.type === 'done') {
                        console.log('Streaming complete');
                    }
                    else if (data.type === 'error') {
                        throw new Error(data.error);
                    }
                }
            }
        }
    } catch (error) {
        console.error('Streaming error:', error);
        contentDiv.innerHTML = `<p>Sorry, I encountered an error: ${escapeHtml(error.message)}. Please try again.</p>`;
    } finally {
        chatInput.disabled = false;
        sendButton.disabled = false;
        chatInput.focus();
    }
}
```

**Event Listener Update**:
```javascript
// In setupEventListeners(), replace:
sendButton.addEventListener('click', sendMessage);

// With:
sendButton.addEventListener('click', sendMessageStream);
```

### CSS Tool Call Styling

```css
/* Tool Call Display Styles */
.tool-call, .tool-result {
    margin: 8px 0;
    padding: 8px 12px;
    border-radius: 4px;
    font-size: 0.9em;
}

.tool-call {
    background-color: #e3f2fd;
    border-left: 3px solid #2196f3;
    color: #0d47a1;
}

.tool-result {
    background-color: #e8f5e9;
    border-left: 3px solid #4caf50;
    color: #1b5e20;
}

.tool-call pre, .tool-result pre {
    margin: 4px 0 0 0;
    padding: 8px;
    background-color: #f5f5f5;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 0.85em;
    color: #1e293b;
}

.tool-call details summary {
    cursor: pointer;
    user-select: none;
    padding: 4px 0;
}

.tool-call details summary:hover {
    opacity: 0.8;
}

.tool-call strong, .tool-result strong {
    display: block;
    margin-bottom: 4px;
}
```

---

## Deployment Considerations

### Nginx Configuration

If deployed behind Nginx, disable buffering for SSE:

```nginx
location /api/v1/chat/stream {
    proxy_pass http://backend:8000;
    proxy_buffering off;  # Critical for SSE
    proxy_cache off;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
}
```

---

## Success Criteria

1. ✅ First content appears within 1-2 seconds (vs 5-30s currently)
2. ✅ Content progressively renders as generated
3. ✅ No breaking changes to existing API (separate endpoint)
4. ✅ All existing tests still pass
5. ✅ New streaming tests achieve >80% coverage
6. ✅ Graceful error handling (network issues, stream interruptions)
7. ✅ Memory efficient (proper stream cleanup)

---

## Potential Challenges & Mitigations

1. **LangGraph Chunk Format**: The structure of chunks from `astream()` may vary
   - **Mitigation**: Test with real agent and adjust parsing logic as needed

2. **Connection Interruptions**: Browser or network issues during streaming
   - **Mitigation**: Proper error boundaries, cleanup in `finally` blocks

3. **Memory Leaks**: Unclosed streams or event listeners
   - **Mitigation**: Ensure reader cleanup and conversation history trimming

4. **Progressive Markdown Rendering Performance**: Re-rendering on every chunk
   - **Mitigation**: Monitor performance; consider debouncing if needed (update every N ms)

---

## Testing Strategy

### Manual Testing Steps

1. **Basic Streaming**:
   - Start backend: `./start_backend.sh`
   - Start frontend: `./start_frontend.sh`
   - Open http://localhost:5500
   - Send message: "What's on the menu?"
   - Verify text streams progressively

2. **Tool Call Streaming**:
   - Send message: "Show me customer information for John Doe"
   - Verify tool call display appears with 🔧 icon
   - Verify tool result appears with ✅ icon
   - Click "Arguments" details to verify expandable section

3. **Error Handling**:
   - Stop backend server
   - Send message
   - Verify error message displays gracefully

4. **Stateless Mode**:
   - Use API client to test stateless streaming
   - Verify no conversation_id in response

### Automated Testing

```python
# tests/test_api_integration.py

async def test_streaming_endpoint():
    """Test streaming chat endpoint."""
    async with httpx.AsyncClient() as client:
        async with connect_sse(
            client, "POST",
            "http://localhost:8000/api/v1/chat/stream",
            json={"message": "Hello", "conversation_id": "test"}
        ) as event_source:
            events = []
            async for sse in event_source.aiter_sse():
                data = json.loads(sse.data)
                events.append(data)
                if data["type"] == "done":
                    break

            # Verify event sequence
            assert events[0]["type"] == "start"
            assert events[-1]["type"] == "done"
            # Verify at least one token event
            assert any(e["type"] == "token" for e in events)
```

---

## Future Enhancements (Out of Scope)

1. **AIRS Integration**: Add security scanning with buffered streaming approach
2. **Reconnection Logic**: Auto-reconnect on connection drop with resume capability
3. **Streaming Toggle**: UI option to switch between streaming and non-streaming modes
4. **Visual Indicators**: Animated cursor during streaming for better UX feedback
5. **Performance Optimization**: Debounced rendering for very fast streams

---

## Notes for Tomorrow

### What Was Completed Today
- ✅ Complete plan created with all technical details
- ✅ All code snippets prepared and ready to copy
- ✅ Design decisions finalized (separate endpoint, tool visibility, no AIRS)
- ✅ Testing strategy defined

### What to Do Tomorrow

1. **Start Fresh**:
   - Review this plan
   - Ensure backend is running: `./start_backend.sh`
   - Check git status is clean

2. **Implement in Order**:
   - Phase 1: Backend ChatService (30 min)
   - Phase 2: Backend API endpoint (30 min)
   - Phase 3: Frontend JavaScript + CSS (1 hour)
   - Phase 4: Testing (1 hour)

3. **Quick Wins First**:
   - Copy code snippets from this plan
   - Test each phase before moving to next
   - Use browser DevTools to debug SSE events

4. **Testing Checklist**:
   - [ ] Basic streaming works
   - [ ] Tool calls display correctly
   - [ ] Error handling works
   - [ ] Existing non-streaming endpoint still works
   - [ ] No memory leaks (check browser memory after 10+ messages)

### Git Commands for Tomorrow

```bash
# Start fresh
git status  # Should show no changes

# Create feature branch
git checkout -b feature/streaming-mode

# After implementation
git add backend/chat_service.py backend/api.py frontend/script.js frontend/style.css
git commit -m "feat: add streaming mode with tool call visibility"

# If needed, update README
git add README.md
git commit -m "docs: document streaming endpoint"
```

---

## Questions or Issues?

If you encounter issues tomorrow:

1. **Streaming not working**:
   - Check browser console for SSE parsing errors
   - Verify backend logs show "Streaming query" messages
   - Use `curl` to test endpoint directly

2. **Tool calls not appearing**:
   - Verify message has `tool_calls` attribute in backend logs
   - Check CSS classes are applied correctly
   - Inspect HTML in browser DevTools

3. **Performance issues**:
   - Check if markdown rendering is slow (consider debouncing)
   - Monitor memory usage in browser
   - Check conversation history isn't growing too large

---

**Good luck tomorrow! This should take 2-3 hours to complete since all the design work is done.** 🚀
