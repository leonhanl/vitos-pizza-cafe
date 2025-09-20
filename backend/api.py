"""FastAPI application for Vito's Pizza Cafe backend."""

import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from .chat_service import get_or_create_chat_service, delete_conversation, list_conversations
from .config import get_logger

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
    conversation_id: Optional[str] = Field(default="default", description="Conversation identifier")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str = Field(..., description="Assistant response")
    conversation_id: str = Field(..., description="Conversation identifier")


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
async def chat(request: ChatRequest):
    """Main chat endpoint for processing user messages."""
    try:
        logger.info(f"Chat request: conversation_id={request.conversation_id}, message_length={len(request.message)}")

        # Get or create chat service for the conversation
        chat_service = get_or_create_chat_service(request.conversation_id)

        # Process the message
        response = chat_service.process_query(request.message)

        logger.info(f"Chat response generated for conversation_id={request.conversation_id}")

        return ChatResponse(
            response=response,
            conversation_id=request.conversation_id
        )

    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing your message: {str(e)}"
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