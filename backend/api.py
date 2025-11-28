"""FastAPI application for Vito's Pizza Cafe backend."""

import logging
import json
from typing import List, Dict, Any, Optional
from uuid import uuid4
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

from .chat_service import get_or_create_chat_service, delete_conversation, list_conversations
from .config import get_logger, Config
from .security.airs_scanner import scan_with_airs

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Vito's Pizza Cafe API",
    description="Backend API for Vito's Pizza Cafe AI Assistant",
    version="1.0.0"
)

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for API requests/responses
class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(..., description="User message to process")
    conversation_id: Optional[str] = Field(default=None, description="Conversation identifier. Omit to start a new conversation.")
    stateless: Optional[bool] = Field(default=False, description="Process request without storing conversation history. Ideal for red teaming and batch testing.")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str = Field(..., description="Assistant response")
    conversation_id: Optional[str] = Field(default=None, description="Conversation identifier (None for stateless requests)")


class ConversationHistory(BaseModel):
    """Model for conversation history."""
    conversation_id: str = Field(..., description="Conversation identifier")
    messages: List[Dict[str, str]] = Field(..., description="List of conversation messages")


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Service status")
    message: str = Field(..., description="Status message")


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Error details")


# API Routes
@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to Vito's Pizza Cafe API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Basic health check - could be expanded to check database, external APIs, etc.
        logger.info("Health check requested")
        return HealthResponse(
            status="healthy",
            message="Vito's Pizza Cafe API is running"
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy"
        )


@app.post("/api/v1/chat", response_model=ChatResponse)
@scan_with_airs
async def chat(request: ChatRequest):
    """Main chat endpoint for processing user messages.

    Supports two modes:
    1. Stateful (default): Maintains conversation history across requests
    2. Stateless: Processes each request independently without storing history
    """
    try:
        # Handle stateless mode - no conversation storage
        if request.stateless:
            logger.info(f"Stateless chat request: message_length={len(request.message)}")

            # Import here to avoid circular dependency
            from .chat_service import ChatService

            # Process without storing conversation
            response = await ChatService.process_stateless_query(request.message)

            logger.info("Stateless chat response generated")

            return ChatResponse(
                response=response,
                conversation_id=None  # No conversation ID for stateless requests
            )

        # Handle stateful mode - with conversation storage
        # Auto-generate conversation_id if not provided
        conversation_id = request.conversation_id or str(uuid4())

        logger.info(f"Stateful chat request: conversation_id={conversation_id}, message_length={len(request.message)}")

        # Get or create chat service for the conversation
        chat_service = get_or_create_chat_service(conversation_id)

        # Process the message asynchronously (FastAPI already runs in an event loop)
        response = await chat_service.aprocess_query(request.message)

        logger.info(f"Stateful chat response generated for conversation_id={conversation_id}")

        return ChatResponse(
            response=response,
            conversation_id=conversation_id
        )

    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing your message: {str(e)}"
        )


@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat endpoint with tool call visibility and AIRS protection.

    Supports two modes:
    1. Stateful (default): Maintains conversation history across requests
    2. Stateless: Processes each request independently without storing history

    Returns:
        StreamingResponse: Server-Sent Events (SSE) stream with event types:
            - start: Initial event with conversation_id
            - token: Text content chunks
            - tool_call: Tool invocation with name and arguments
            - tool_result: Tool execution results
            - done: Stream completion
            - error: Error messages
            - security_violation: Content blocked by security policy
    """
    # Input scan before streaming begins
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

    conversation_id = request.conversation_id or str(uuid4())

    if request.stateless:
        # Stateless mode - no conversation storage
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

    # Stateful mode - with conversation storage
    logger.info(f"Streaming chat request: conversation_id={conversation_id}, message_length={len(request.message)}")

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


@app.get("/api/v1/conversations", response_model=List[str])
async def get_conversations():
    """Get list of active conversation IDs."""
    try:
        conversations = list_conversations()
        logger.info(f"Retrieved {len(conversations)} active conversations")
        return conversations
    except Exception as e:
        logger.error(f"Error retrieving conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving conversations"
        )


@app.get("/api/v1/conversations/{conversation_id}/history", response_model=ConversationHistory)
async def get_conversation_history(conversation_id: str):
    """Get conversation history for a specific conversation."""
    try:
        chat_service = get_or_create_chat_service(conversation_id)
        history = chat_service.get_conversation_history()

        logger.info(f"Retrieved history for conversation_id={conversation_id}, messages={len(history)}")

        return ConversationHistory(
            conversation_id=conversation_id,
            messages=history
        )

    except Exception as e:
        logger.error(f"Error retrieving conversation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving conversation history"
        )


@app.delete("/api/v1/conversations/{conversation_id}")
async def delete_conversation_endpoint(conversation_id: str):
    """Delete a conversation and its history."""
    try:
        deleted = delete_conversation(conversation_id)

        if deleted:
            logger.info(f"Deleted conversation_id={conversation_id}")
            return {"message": f"Conversation {conversation_id} deleted successfully"}
        else:
            logger.warning(f"Conversation not found: {conversation_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting conversation"
        )


@app.post("/api/v1/conversations/{conversation_id}/clear")
async def clear_conversation_history(conversation_id: str):
    """Clear conversation history while keeping the conversation active."""
    try:
        chat_service = get_or_create_chat_service(conversation_id)
        chat_service.clear_history()

        logger.info(f"Cleared history for conversation_id={conversation_id}")
        return {"message": f"Conversation {conversation_id} history cleared successfully"}

    except Exception as e:
        logger.error(f"Error clearing conversation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error clearing conversation history"
        )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error"
    )


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the FastAPI server."""
    logger.info(f"Starting Vito's Pizza Cafe API server on {host}:{port}")
    uvicorn.run(
        "src.backend.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    # Initialize logger
    get_logger()
    # Run the server
    run_server(reload=True)