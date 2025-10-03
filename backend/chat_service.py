"""Chat service for Vito's Pizza Cafe application."""

import logging
import asyncio
from typing import List, Optional, Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent

from .config import logger
from .knowledge_base import retrieve_context
from .database import get_database_tools
from .llm import get_llm
from .mcp_tools import get_mcp_tools

logger = logging.getLogger(__name__)

# System prompt for Vito's Pizza Cafe
SYSTEM_PROMPT = """You are the intelligent assistant for Vito's Pizza Cafe, well-versed in the company background, account management, menus and orders, delivery and pickup, dining, and payment information. Please provide users with precise answers regarding registration, login, order inquiries, placing orders, discounts, and refund policies, always offering help in a friendly and professional tone and responding in the language used in the user's query. For questions beyond the above scope, please inform the user that you can only provide information related to the aforementioned services, and suggest that they contact the in-store staff or visit the official website for further assistance. Use the following content as the knowledge you have learned, enclosed within <context></context> XML tags. When you need to reference the content in the context, please use the original text without any arbitrary modifications, including URL addresses, etc."""


class ChatService:
    """Service for handling chat conversations with Vito's Pizza Cafe assistant."""

    def __init__(self, conversation_id: str = "default"):
        """Initialize chat service with conversation ID."""
        self.conversation_id = conversation_id
        self.conversation_history = []
        logger.info(f"ChatService initialized with conversation_id: {conversation_id}")

    def process_query(self, user_input: str) -> str:
        """Process user query with mandatory RAG retrieval + React agent.

        This is a synchronous wrapper around the async implementation.
        """
        return asyncio.run(self.aprocess_query(user_input))

    async def aprocess_query(self, user_input: str) -> str:
        """Process user query with mandatory RAG retrieval + React agent (async version)."""
        logger.info(f"Processing query: {user_input}, Conversation ID: {self.conversation_id}")

        try:
            # 1. Always retrieve context first (mandatory RAG)
            context = retrieve_context(user_input)
            logger.debug(f"Retrieved context for query: {user_input}")

            # 2. Get LLM instance
            llm = get_llm()

            # 3. Get database tools
            db_tools = get_database_tools(llm)

            # 4. Get MCP tools (async)
            mcp_tools = await get_mcp_tools()

            # 5. Combine all tools
            tools = db_tools + mcp_tools
            logger.info(f"Total tools available: {len(tools)} (DB: {len(db_tools)}, MCP: {len(mcp_tools)})")

            # 6. Create React agent
            react_agent = create_react_agent(
                model=llm,
                tools=tools
            )

            # 7. Prepare messages
            messages = []

            # Add system prompt with context
            system_message = f"{SYSTEM_PROMPT}\n\n{context}"
            messages.append(SystemMessage(content=system_message))

            # Add conversation history if provided
            if self.conversation_history:
                messages.extend(self.conversation_history)

            # Add current user query
            messages.append(HumanMessage(content=user_input))

            # 8. Get response from React agent
            result = react_agent.invoke({"messages": messages})
            response = result["messages"][-1].content

            # 9. Update conversation history
            self.conversation_history.append(HumanMessage(content=user_input))
            self.conversation_history.append(AIMessage(content=response))

            logger.debug(f"Generated response: {response[:100]}...")
            return response

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return "I apologize, but I encountered an error while processing your request. Please try again or contact our support team."

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get conversation history in a serializable format."""
        history = []
        for i in range(0, len(self.conversation_history), 2):
            if i + 1 < len(self.conversation_history):
                user_msg = self.conversation_history[i]
                assistant_msg = self.conversation_history[i + 1]
                history.append({
                    "user": user_msg.content,
                    "assistant": assistant_msg.content
                })
        return history

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history = []
        logger.info(f"Cleared conversation history for: {self.conversation_id}")


# Global conversation store for API usage
_conversations: Dict[str, ChatService] = {}


def get_or_create_chat_service(conversation_id: str = "default") -> ChatService:
    """Get existing chat service or create new one."""
    if conversation_id not in _conversations:
        _conversations[conversation_id] = ChatService(conversation_id)
    return _conversations[conversation_id]


def delete_conversation(conversation_id: str) -> bool:
    """Delete a conversation."""
    if conversation_id in _conversations:
        del _conversations[conversation_id]
        logger.info(f"Deleted conversation: {conversation_id}")
        return True
    return False


def list_conversations() -> List[str]:
    """List all active conversation IDs."""
    return list(_conversations.keys())


logger.info("Chat service initialized")