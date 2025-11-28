# Design Document: Streaming AIRS Protection with Progressive Scanning

**Date**: 2025-11-28
**Author**: Claude Code
**Status**: Approved

---

## Executive Summary

This document outlines the design for implementing Prisma AIRS (AI Runtime Security) protection for the streaming API endpoint (`/api/v1/chat/stream`) in Vito's Pizza Cafe. The implementation uses progressive content accumulation with interval-based scanning and immediate content retraction upon detection of malicious output.

### Key Features
- Token-by-token progressive streaming UX maintained
- Scan accumulated content every 50 tokens (configurable)
- Immediate content retraction when malicious content detected
- Both input and output scanning
- Fail-open behavior for availability
- Applies to both stateful and stateless streaming modes

---

## 1. Objective

Implement Prisma AIRS security scanning for the streaming API endpoint with progressive content accumulation and immediate content retraction upon detection of malicious output, while maintaining the existing streaming user experience.

---

## 2. Requirements

### Functional Requirements
1. ✅ Maintain token-by-token progressive streaming UX
2. ✅ Scan accumulated content at intervals (not just final output)
3. ✅ Immediately stop streaming and retract displayed content when malicious content detected
4. ✅ Both input and output scanning required
5. ✅ Apply to both stateful and stateless streaming modes

### Non-Functional Requirements
1. ✅ Fail-open behavior when AIRS API fails (prioritize availability)
2. ✅ Configurable scan interval for security/cost trade-offs
3. ✅ Comprehensive security logging with streaming context
4. ✅ Minimal latency impact on user experience

---

## 3. Architecture Overview

### 3.1 Current State

**Blocking Mode** (`/api/v1/chat`):
- Protected with `@scan_with_airs` decorator
- Input scan before processing
- Output scan after complete response generated
- HTTP 403 if either scan blocks

**Streaming Mode** (`/api/v1/chat/stream`):
- ❌ No AIRS protection (vulnerability)
- Streams events: `start` → `kb_search` → `token` (many) → `tool_call` → `tool_result` → `done`

**Frontend**:
- Accumulates tokens in `accumulatedContent` variable
- Renders progressively using `marked.parse()`

### 3.2 Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Input                              │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
                    ┌────────────────────┐
                    │   Input Scan       │
                    │   (AIRS API)       │
                    └────────┬───────────┘
                             ↓
                    ┌────────────────────┐
                    │  Stream Response   │
                    │  (token by token)  │
                    └────────┬───────────┘
                             ↓
                    ┌────────────────────┐
                    │ Accumulate Tokens  │
                    │ (chunk1-N)         │
                    └────────┬───────────┘
                             ↓
                    ┌────────────────────┐
                    │ Every 50 tokens    │
                    │ → Output Scan      │
                    │   (AIRS API)       │
                    └────────┬───────────┘
                             ↓
                    ┌────────────────────┐
                    │ If BLOCK detected: │
                    │ - Stop streaming   │
                    │ - Yield violation  │
                    │ - Retract content  │
                    └────────┬───────────┘
                             ↓
                    ┌────────────────────┐
                    │ Else: Continue     │
                    └────────────────────┘
```

### 3.3 Data Flow

1. **User Input** → **Input Scan** (blocks malicious prompts before processing)
2. **LLM Generation** → **Stream tokens** (progressive display)
3. **Accumulate tokens** → **Scan every N tokens** (early threat detection)
4. **If malicious** → **security_violation event** → **Frontend retracts content**
5. **If benign** → **Continue streaming** → **Final scan** → **Done**

---

## 4. Implementation Details

### 4.1 Backend Changes

#### 4.1.1 Add Input Scanning to Streaming Endpoint

**File**: `backend/api.py`
**Location**: `/api/v1/chat/stream` endpoint (line 151)

**Changes**:
```python
@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat endpoint with AIRS protection."""

    # NEW: Input scan before streaming begins
    if Config.AIRS_ENABLED:
        from .security.airs_scanner import scan_input, log_security_violation

        input_result = await scan_input(
            prompt=request.message,
            profile_name=Config.X_PAN_INPUT_CHECK_PROFILE_NAME
        )

        if input_result.action == "block":
            log_security_violation(
                scan_type="input",
                category=input_result.category,
                action="block",
                profile_name=Config.X_PAN_INPUT_CHECK_PROFILE_NAME,
                content=request.message,
                conversation_id=getattr(request, 'conversation_id', None)
            )

            raise HTTPException(
                status_code=403,
                detail="Your request couldn't be processed due to our content policy."
            )

    # Continue with existing streaming logic
    ...
```

#### 4.1.2 Implement Progressive Output Scanning

**File**: `backend/chat_service.py`
**Methods**: `aprocess_query_stream()` and `process_stateless_query_stream()`

**Scanning Strategy**:
- **Scan interval**: Every 50 tokens (token-based)
- **Accumulation**: Track all text tokens streamed so far
- **Scan content**: Full accumulated text (chunk1-N, not just new chunks)
- **Failure mode**: Fail-open (continue streaming if AIRS API fails)
- **Scope**: Apply to both stateful and stateless streaming modes

**Implementation**:
```python
async def aprocess_query_stream(self, user_input: str) -> AsyncIterator[Dict[str, Any]]:
    """Stream response with progressive AIRS scanning."""

    # ... existing setup code ...

    accumulated_response = ""
    token_count = 0

    async for chunk in react_agent.astream(
        {"messages": messages},
        config={"callbacks": [ToolLoggingHandler()]},
        stream_mode="messages"
    ):
        # ... existing chunk processing ...

        if isinstance(message, AIMessage) and message.content:
            content_chunk = message.content
            accumulated_response += content_chunk
            token_count += 1

            # Yield token to frontend
            yield {"type": "token", "content": content_chunk}

            # Progressive scanning every N tokens
            if token_count % Config.AIRS_STREAM_SCAN_TOKEN_INTERVAL == 0 and Config.AIRS_ENABLED:
                try:
                    from .security.airs_scanner import scan_output, log_security_violation

                    scan_result = await scan_output(
                        response=accumulated_response,
                        profile_name=Config.X_PAN_OUTPUT_CHECK_PROFILE_NAME
                    )

                    if scan_result.action == "block":
                        # Log violation
                        log_security_violation(
                            scan_type="output",
                            category=scan_result.category,
                            action="block",
                            profile_name=Config.X_PAN_OUTPUT_CHECK_PROFILE_NAME,
                            content=accumulated_response,
                            conversation_id=self.conversation_id,
                            scan_context="progressive",
                            tokens_accumulated=token_count
                        )

                        # Yield security violation event
                        yield {
                            "type": "security_violation",
                            "message": "Response blocked due to content policy"
                        }

                        # Stop streaming immediately
                        return

                except Exception as e:
                    # Fail-open: log error and continue streaming
                    logger.error(f"AIRS scan failed during streaming: {e}")
                    # Continue without blocking

    # Final scan after streaming completes
    if Config.AIRS_ENABLED and accumulated_response:
        try:
            final_scan_result = await scan_output(
                response=accumulated_response,
                profile_name=Config.X_PAN_OUTPUT_CHECK_PROFILE_NAME
            )

            if final_scan_result.action == "block":
                log_security_violation(
                    scan_type="output",
                    category=final_scan_result.category,
                    action="block",
                    profile_name=Config.X_PAN_OUTPUT_CHECK_PROFILE_NAME,
                    content=accumulated_response,
                    conversation_id=self.conversation_id,
                    scan_context="final",
                    tokens_accumulated=token_count
                )

                yield {
                    "type": "security_violation",
                    "message": "Response blocked due to content policy"
                }
                return

        except Exception as e:
            logger.error(f"AIRS final scan failed: {e}")

    # Update conversation history
    self.conversation_history.append(HumanMessage(content=user_input))
    self.conversation_history.append(AIMessage(content=accumulated_response))
```

**Note**: Same logic applies to `process_stateless_query_stream()` with `conversation_id=None`

#### 4.1.3 Configuration Updates

**File**: `backend/config.py`

**Add** (after line 51):
```python
# AIRS Streaming Scan Configuration
AIRS_STREAM_SCAN_TOKEN_INTERVAL = int(os.getenv("AIRS_STREAM_SCAN_TOKEN_INTERVAL", "50"))
```

**File**: `.env.example`

**Add**:
```bash
# AIRS Streaming Configuration
AIRS_STREAM_SCAN_TOKEN_INTERVAL=50  # Scan every N tokens
```

#### 4.1.4 Enhanced Security Logging

**File**: `backend/security/airs_scanner.py`

**Update signature**:
```python
def log_security_violation(
    scan_type: str,
    category: str,
    action: str,
    profile_name: str,
    content: str,
    conversation_id: Optional[str] = None,
    scan_context: Optional[str] = None,  # NEW: "progressive" or "final"
    tokens_accumulated: Optional[int] = None  # NEW: token count at detection
) -> None:
    """Log detailed security violation for monitoring and audit."""
    logger.warning(
        f"AIRS Security Violation - "
        f"scan_type={scan_type}, "
        f"scan_context={scan_context}, "
        f"tokens_accumulated={tokens_accumulated}, "
        f"category={category}, "
        f"action={action}, "
        f"profile={profile_name}, "
        f"conversation_id={conversation_id}, "
        f"content_length={len(content)}"
    )
```

---

### 4.2 Frontend Changes

#### 4.2.1 Add Content Retraction Handler

**File**: `frontend/script.js`
**Function**: `sendMessageStream()`
**Location**: Line 199-314

**Changes**:

1. **Add security_violation event handler** (after line 296):
```javascript
else if (data.type === 'security_violation') {
    // Clear accumulated content
    accumulatedContent = "";
    toolCallsHtml = "";

    // Retract all displayed content and show error
    contentDiv.innerHTML = `
        <div class="security-error">
            <span class="error-icon">⚠️</span>
            <p><strong>Response Blocked</strong></p>
            <p>The response couldn't be displayed due to our content policy.</p>
            <p>Please try rephrasing your question.</p>
        </div>
    `;
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Stop processing further events
    break;
}
```

#### 4.2.2 Add Security Error Styling

**File**: `frontend/style.css`

**Add**:
```css
/* Security Error Styling */
.security-error {
    background: #fff3cd;
    border: 2px solid #ffc107;
    border-radius: 8px;
    padding: 16px;
    margin: 8px 0;
    text-align: center;
}

.security-error .error-icon {
    font-size: 32px;
    display: block;
    margin-bottom: 8px;
}

.security-error p {
    margin: 4px 0;
    color: #856404;
}

.security-error strong {
    color: #d39e00;
}
```

---

### 4.3 Event Stream Updates

#### 4.3.1 New Event Type: `security_violation`

**Format**:
```json
{
    "type": "security_violation",
    "message": "Response blocked due to content policy"
}
```

**When sent**: When AIRS scan detects `action: "block"` (either progressive or final scan)

#### 4.3.2 Updated Event Flow

**Normal flow** (benign content):
```
start → kb_search → token → token → ... → token → done
```

**Blocked flow** (malicious content detected):
```
start → kb_search → token → token → ... → token
                                            ↓
                                    [Scan at interval]
                                            ↓
                                   Malicious detected
                                            ↓
                                   security_violation → STOP
```

---

## 5. Files to Modify

### Backend
1. ✅ `backend/api.py` - Add input scan to streaming endpoint
2. ✅ `backend/chat_service.py` - Implement progressive scanning in both streaming methods
3. ✅ `backend/config.py` - Add streaming scan configuration
4. ✅ `backend/security/airs_scanner.py` - Enhance logging for streaming context
5. ✅ `.env.example` - Document new configuration options

### Frontend
1. ✅ `frontend/script.js` - Add security_violation handler with content retraction
2. ✅ `frontend/style.css` - Add security error styling

---

## 6. Testing Strategy

### 6.1 Unit Tests

**File**: `tests/unit/test_streaming_airs.py` (new file)

**Test cases**:
1. ✅ Test input scan blocks malicious prompt before streaming (both stateful and stateless)
2. ✅ Test progressive scan detects malicious content at token interval (both modes)
3. ✅ Test final scan detects malicious content in last tokens (both modes)
4. ✅ Test benign content passes all scans
5. ✅ Test scan interval timing (token-based)
6. ✅ Test security_violation event format
7. ✅ Test fail-open behavior when AIRS API fails (simulate network error)

### 6.2 Integration Tests

**File**: `tests/test_streaming_airs_integration.py` (new file)

**Test cases**:
1. ✅ End-to-end streaming with malicious content detection
2. ✅ Frontend retraction behavior (requires browser automation)
3. ✅ AIRS API call count verification (ensure not too many scans)
4. ✅ Performance impact measurement

### 6.3 Manual Testing Scenarios

1. ✅ Inject prompt injection after 100 tokens
2. ✅ Test PII disclosure scenario (progressive detection)
3. ✅ Test data poisoning (malicious URLs in response)
4. ✅ Verify content retraction UX (smooth transition)

---

## 7. Performance Considerations

### 7.1 AIRS API Call Optimization

**Current** (blocking mode):
- 1 input scan + 1 output scan = 2 AIRS API calls per request

**New** (streaming mode):
- 1 input scan + ~N/50 progressive scans + 1 final scan
- **Example**: 500-token response = 1 + 10 + 1 = 12 AIRS API calls

**Mitigation strategies**:
1. ✅ Configurable scan interval (balance security vs. cost)
2. ✅ Skip progressive scanning for very short responses (<50 tokens)
3. ✅ Final scan only if not already scanned at last interval

### 7.2 Latency Impact

- **AIRS scan time**: ~200-500ms per API call
- **User perception**: Slight pause every 50 tokens
- **Mitigation**: Async scanning (non-blocking, streaming continues during scan)

### 7.3 Configuration Profiles

**Default Settings** (Balanced):
```bash
AIRS_STREAM_SCAN_TOKEN_INTERVAL=50  # Scan every 50 tokens
```

**High-Security Settings** (More Frequent):
```bash
AIRS_STREAM_SCAN_TOKEN_INTERVAL=20  # Scan every 20 tokens (faster detection)
```

**Cost-Optimized Settings** (Less Frequent):
```bash
AIRS_STREAM_SCAN_TOKEN_INTERVAL=100  # Scan every 100 tokens (fewer API calls)
```

---

## 8. Edge Cases

| Edge Case | Handling Strategy |
|-----------|------------------|
| **Empty response** | Skip scanning if no tokens accumulated |
| **Very short responses** (<50 tokens) | Skip progressive scan, do final scan only |
| **AIRS API failure** | Fail-open: log error, continue streaming |
| **Network interruption** | Frontend handles disconnection gracefully (existing behavior) |
| **Multiple violations** | Stop at first detection, don't continue scanning |

---

## 9. Success Criteria

1. ✅ Malicious content detected and retracted within 50 tokens of appearance
2. ✅ User sees sanitized error message instead of malicious content
3. ✅ No degradation in streaming UX for benign content
4. ✅ AIRS API usage stays within acceptable cost limits
5. ✅ All existing security test cases pass with streaming mode
6. ✅ Logging captures all security violations with streaming context

---

## 10. Rollout Plan

### Phase 1: Implementation
1. ✅ Backend changes (progressive scanning)
2. ✅ Frontend changes (retraction handler)
3. ✅ Configuration updates
4. ✅ Unit tests

### Phase 2: Testing
1. ✅ Integration tests
2. ✅ Manual security testing (all attack vectors)
3. ✅ Performance profiling

### Phase 3: Deployment
1. ✅ Deploy to staging environment
2. ✅ Monitor AIRS API usage and costs
3. ✅ Gather user feedback on UX
4. ✅ Tune scan intervals if needed
5. ✅ Deploy to production

---

## 11. Dependencies

- ✅ `aisecurity` SDK (already installed)
- ✅ AIRS API credentials (already configured)
- ✅ No new dependencies required

---

## 12. Estimated Implementation Time

| Phase | Estimated Time |
|-------|---------------|
| Backend implementation | 3-4 hours |
| Frontend implementation | 1-2 hours |
| Testing and validation | 2-3 hours |
| Documentation updates | 1 hour |
| **Total** | **7-10 hours** |

---

## 13. Security Considerations

### 13.1 Threat Model

**Threats Mitigated**:
- ✅ Prompt injection (input scan)
- ✅ PII disclosure (progressive output scan)
- ✅ Data poisoning (progressive output scan)
- ✅ Toxic content generation (progressive output scan)

**Threats NOT Fully Mitigated**:
- ⚠️ Brief exposure to malicious content (first 50 tokens before scan)
  - **Mitigation**: Configurable to 20 tokens for high-security scenarios

### 13.2 Attack Vectors Tested

1. **Prompt Injection**: System prompt leak attempts
2. **PII Disclosure**: Customer data extraction
3. **Data Poisoning**: Malicious URLs in responses
4. **Goal Hijacking**: Attempting to change assistant behavior

---

## 14. Monitoring and Observability

### 14.1 Metrics to Track

- AIRS API call count per request
- Progressive scan hit rate (how often scans detect threats)
- Final scan hit rate
- Average tokens before detection
- AIRS API latency
- Fail-open rate (AIRS API failures)

### 14.2 Logging

All security violations logged with:
- `scan_type`: "input" or "output"
- `scan_context`: "progressive" or "final"
- `tokens_accumulated`: Token count at detection
- `category`: AIRS violation category
- `conversation_id`: For tracking
- `content_length`: Size of blocked content

---

## 15. Future Enhancements

### 15.1 Potential Improvements

1. **Adaptive scan intervals**: Adjust frequency based on content risk signals
2. **Client-side token estimation**: Show user approximate cost before streaming
3. **Scan result caching**: Skip re-scanning identical content
4. **Progressive confidence scoring**: Show user "security confidence" meter

### 15.2 Alternative Approaches Considered

1. **Post-stream validation only**: Simpler but allows full malicious content display
2. **Hybrid (time + token)**: More complex, minimal benefit over token-based
3. **Block streaming entirely when AIRS enabled**: Simplest but poor UX

---

## 16. Approval and Sign-off

**Approved by**: User
**Date**: 2025-11-28
**Status**: Ready for Implementation

**Key Decisions**:
- ✅ Chunk-based scanning (every 50 content chunks, not LLM tokens)
- ✅ Synchronous blocking scans (simpler, acceptable latency)
- ✅ Always perform final scan (no optimization)
- ✅ Record user input only when content blocked (audit trail)
- ✅ Scan LLM output only (not tool calls/results)
- ✅ Fail-open behavior for availability
- ✅ Apply to both stateful and stateless modes
- ✅ Content retraction on detection (not just flagging)

---

## 17. Approved Design Decisions (Implementation Clarifications)

During implementation planning, the following design decisions were made to resolve ambiguities in the original design:

### Decision 1: Token Counting Mechanism
**Decision**: Use LangGraph content chunks (not actual LLM tokens)

**Rationale**:
- LangGraph's `stream_mode="messages"` yields variable-size content chunks
- No need for `tiktoken` tokenization overhead
- For security purposes, chunk-based scanning is sufficient
- Simpler implementation, no new dependencies

**Implementation**: Use `AIRS_STREAM_SCAN_CHUNK_INTERVAL=50` (terminology change: "token" → "chunk")

### Decision 2: Scanning Synchronicity
**Decision**: Synchronous (blocking) scanning

**Rationale**:
- Correctness first - simpler implementation
- AIRS API typically responds in 200-500ms - acceptable latency
- Fail-open helps if AIRS API is slow
- Can optimize to async later if profiling shows UX issues

**Implementation**: `await scan_output(...)` blocks streaming briefly every 50 chunks

### Decision 3: Conversation History Handling
**Decision**: Record user input only when content is blocked

**Rationale**:
- Maintains audit trail of user inputs
- Blocked responses are not persisted (no malicious content stored)
- Clean state for next message
- API consistency - history shows only allowed exchanges

**Implementation**:
```python
if scan_result.action == "block":
    # Record user input for audit
    self.conversation_history.append(HumanMessage(content=user_input))
    # Do NOT record blocked response
    yield {"type": "security_violation", ...}
    return
```

### Decision 4: Tool Content Scanning Scope
**Decision**: Only scan LLM text output at two levels:
- **Input scan**: At `api.py` endpoint level (before processing)
- **Output scan**: At `chat_service.py` streaming methods (LLM `token` events only)

**Out of scope for this implementation**:
- Tool call arguments scanning
- Tool result scanning
- Knowledge base retrieval content scanning

**Rationale**:
- Primary threat is LLM-generated content (prompt injection, PII disclosure)
- Tool results already constrained by database schema and MCP tool security
- Performance trade-off - scanning all tool results increases AIRS API calls significantly
- Can add tool scanning later if threat model requires it

### Decision 5: Final Scan Strategy
**Decision**: Always scan the final complete message (no optimization)

**Rationale**:
- Simplicity over cost optimization
- Guarantees complete content is scanned
- Eliminates edge case logic for "recently scanned" thresholds
- Final scan ensures no malicious content in last chunks

**Implementation**: Always perform final scan after streaming completes, regardless of when last progressive scan occurred

---

## Appendix A: Configuration Reference

```bash
# AIRS Core Configuration
AIRS_ENABLED=true
X_PAN_TOKEN=your_airs_api_token_here
X_PAN_INPUT_CHECK_PROFILE_NAME=Demo-Profile-for-Input
X_PAN_OUTPUT_CHECK_PROFILE_NAME=Demo-Profile-for-Output

# AIRS Streaming Configuration
AIRS_STREAM_SCAN_CHUNK_INTERVAL=50  # Scan every N content chunks (LangGraph message chunks)
```

---

## Appendix B: API Reference

### New Event Type

**Event**: `security_violation`

**Structure**:
```typescript
{
    type: "security_violation",
    message: string  // User-friendly error message
}
```

**When triggered**:
- Progressive scan detects malicious content
- Final scan detects malicious content in last tokens

**Frontend behavior**:
- Clear accumulated content
- Display security error message
- Stop processing further events

---

**End of Design Document**
