"""Chat service for Vito's Pizza Cafe application."""

import logging
import asyncio
from typing import List, Optional, Dict, Any, AsyncIterator
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from .config import logger
from .knowledge_base import retrieve_context
from .database import get_database_tools
from .llm import get_llm
from .mcp_tools import get_mcp_tools
from .callbacks import ToolLoggingHandler

logger = logging.getLogger(__name__)

# System prompt for Vito's Pizza Cafe
SYSTEM_PROMPT = """You are the intelligent assistant for Vito's Pizza Cafe, well-versed in the company background, account management, menus and orders, delivery and pickup, dining, and payment information. Please provide users with precise answers regarding registration, login, order inquiries, placing orders, discounts, and refund policies, always offering help in a friendly and professional tone and responding in the language used in the user's query. For questions beyond the above scope, please inform the user that you can only provide information related to the aforementioned services, and suggest that they contact the in-store staff or visit the official website for further assistance. Use the following content as the knowledge you have learned, enclosed within <context></context> XML tags. When you need to reference the content in the context, please use the original text without any arbitrary modifications, including URL addresses, etc. When calculating, please make sure to write python code and use code-sandbox-mcp tools to ensure accuracy, no matter how simple it is."""


def get_tool_description(tool_name: str, all_tools: list) -> str:
    """Extract friendly description from tool definition.

    Args:
        tool_name: Name of the tool to look up
        all_tools: List of all available tools

    Returns:
        Tool description string, or fallback message if not found
    """
    for tool in all_tools:
        # Check if tool has a name attribute matching our search
        if hasattr(tool, 'name') and tool.name == tool_name:
            # Try to get description from various possible locations
            if hasattr(tool, 'description') and tool.description:
                return tool.description
            if hasattr(tool, 'metadata') and isinstance(tool.metadata, dict):
                desc = tool.metadata.get('description')
                if desc:
                    return desc

    # Fallback message
    return "正在处理请求..."


class ChatService:
    """Service for handling chat conversations with Vito's Pizza Cafe assistant.

    Note: This class has 4 similar methods with intentional duplication for clarity:
    - aprocess_query / aprocess_query_stream: Stateful (with conversation history)
    - process_stateless_query / process_stateless_query_stream: Stateless (no history)

    The duplication is intentional to keep each method self-contained and readable.
    When modifying tool setup, remember to update all 4 methods consistently.
    """

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
            result = await react_agent.ainvoke(
                {"messages": messages},
                config={"callbacks": [ToolLoggingHandler()]}
            )
            response = result["messages"][-1].content

            # 9. Update conversation history
            self.conversation_history.append(HumanMessage(content=user_input))
            self.conversation_history.append(AIMessage(content=response))

            logger.debug(f"Generated response: {response[:100]}...")
            return response

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return "I apologize, but I encountered an error while processing your request. Please try again or contact our support team."

    async def aprocess_query_stream(self, user_input: str) -> AsyncIterator[Dict[str, Any]]:
        """Stream response chunks including tool calls."""
        logger.info(f"Streaming query: {user_input}, Conversation ID: {self.conversation_id}")

        try:
            # 1. Always retrieve context first (mandatory RAG)
            # Yield knowledge base search event
            yield {
                "type": "kb_search",
                "message": "Searching knowledge base..."
            }

            context = retrieve_context(user_input)
            logger.debug(f"Retrieved context for streaming query: {user_input}")

            # 2. Get LLM instance
            llm = get_llm()

            # 3. Get database tools
            db_tools = get_database_tools(llm)

            # 4. Get MCP tools (async)
            mcp_tools = await get_mcp_tools()

            # 5. Combine all tools
            tools = db_tools + mcp_tools
            logger.info(f"Total tools available for streaming: {len(tools)} (DB: {len(db_tools)}, MCP: {len(mcp_tools)})")

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

            # 8. Stream response from React agent
            accumulated_response = ""
            chunk_count = 0
            content_chunk_count = 0  # Track content chunks separately

            async for chunk in react_agent.astream(
                {"messages": messages},
                config={"callbacks": [ToolLoggingHandler()]},
                stream_mode="messages"
            ):
                chunk_count += 1
                # Chunk format with stream_mode="messages": (message, metadata)
                if len(chunk) == 2:
                    message, metadata = chunk

                    # Handle AIMessage (agent response or tool calls)
                    if isinstance(message, AIMessage):
                        # Check for tool calls first
                        if hasattr(message, 'tool_calls') and message.tool_calls and len(message.tool_calls) > 0:
                            # Tool invocation - yield friendly description for UI
                            for tool_call in message.tool_calls:
                                tool_name = tool_call.get("name", "")

                                # Skip empty tool names (streaming artifacts)
                                if not tool_name:
                                    continue

                                # Get friendly description from tool definition
                                tool_description = get_tool_description(tool_name, tools)

                                yield {
                                    "type": "tool_call",
                                    "tool": tool_name,  # Keep for logging/debugging
                                    "description": tool_description  # Use for customer-facing display
                                }
                        # Check for content (can have both tool_calls and content)
                        if message.content:
                            # Agent text response - yield token
                            content_chunk = message.content
                            accumulated_response += content_chunk
                            content_chunk_count += 1

                            yield {
                                "type": "token",
                                "content": content_chunk
                            }

                            # Progressive scanning every N chunks
                            from .config import Config
                            if content_chunk_count % Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL == 0 and Config.AIRS_ENABLED:
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
                                            chunks_accumulated=content_chunk_count
                                        )

                                        # Record user input for audit (per Decision 3)
                                        self.conversation_history.append(HumanMessage(content=user_input))

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

                    # Handle ToolMessage (tool results)
                    elif isinstance(message, ToolMessage):
                        yield {
                            "type": "tool_result",
                            "tool_call_id": message.tool_call_id,
                            "result": message.content
                        }

            # Final scan after streaming completes (per Decision 5)
            from .config import Config
            if Config.AIRS_ENABLED and accumulated_response:
                try:
                    from .security.airs_scanner import scan_output, log_security_violation

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
                            chunks_accumulated=content_chunk_count
                        )

                        # Record user input for audit
                        self.conversation_history.append(HumanMessage(content=user_input))

                        yield {
                            "type": "security_violation",
                            "message": "Response blocked due to content policy"
                        }
                        return

                except Exception as e:
                    logger.error(f"AIRS final scan failed: {e}")

            # 9. Update conversation history after streaming completes (only if not blocked)
            self.conversation_history.append(HumanMessage(content=user_input))
            self.conversation_history.append(AIMessage(content=accumulated_response))

            logger.debug(f"Streaming complete: {accumulated_response}")
            logger.debug(f"Total chunks streamed: {chunk_count}")

        except Exception as e:
            logger.error(f"Error streaming query: {e}")
            yield {
                "type": "error",
                "error": str(e)
            }

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

    @staticmethod
    async def process_stateless_query(user_input: str) -> str:
        """Process a single query without storing conversation history.

        This is ideal for red teaming and batch testing scenarios where
        conversation history is not needed and memory usage should be minimized.

        Args:
            user_input: The user's query to process

        Returns:
            The assistant's response
        """
        logger.info(f"Processing stateless query: {user_input}")

        try:
            # 1. Retrieve context (mandatory RAG)
            context = retrieve_context(user_input)
            logger.debug(f"Retrieved context for stateless query: {user_input}")

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

            # 7. Prepare messages (no conversation history)
            system_message = f"{SYSTEM_PROMPT}\n\n{context}"
            messages = [
                SystemMessage(content=system_message),
                HumanMessage(content=user_input)
            ]

            # 8. Get response from React agent
            result = await react_agent.ainvoke(
                {"messages": messages},
                config={"callbacks": [ToolLoggingHandler()]}
            )
            response = result["messages"][-1].content

            logger.debug(f"Generated stateless response: {response[:100]}...")
            return response

        except Exception as e:
            logger.error(f"Error processing stateless query: {e}")
            return "I apologize, but I encountered an error while processing your request. Please try again or contact our support team."

    @staticmethod
    async def process_stateless_query_stream(user_input: str) -> AsyncIterator[Dict[str, Any]]:
        """Stream response for a single query without storing conversation history.

        This is ideal for red teaming and batch testing scenarios where
        conversation history is not needed and memory usage should be minimized.

        Args:
            user_input: The user's query to process

        Yields:
            Event dictionaries with streaming updates
        """
        logger.info(f"Processing stateless streaming query: {user_input}")

        try:
            # 1. Retrieve context (mandatory RAG)
            # Yield knowledge base search event
            yield {
                "type": "kb_search",
                "message": "Searching knowledge base..."
            }

            context = retrieve_context(user_input)
            logger.debug(f"Retrieved context for stateless streaming query: {user_input}")

            # 2. Get LLM instance
            llm = get_llm()

            # 3. Get database tools
            db_tools = get_database_tools(llm)

            # 4. Get MCP tools (async)
            mcp_tools = await get_mcp_tools()

            # 5. Combine all tools
            tools = db_tools + mcp_tools
            logger.info(f"Total tools available for stateless streaming: {len(tools)} (DB: {len(db_tools)}, MCP: {len(mcp_tools)})")

            # 6. Create React agent
            react_agent = create_react_agent(
                model=llm,
                tools=tools
            )

            # 7. Prepare messages (no conversation history)
            system_message = f"{SYSTEM_PROMPT}\n\n{context}"
            messages = [
                SystemMessage(content=system_message),
                HumanMessage(content=user_input)
            ]

            # 8. Stream response from React agent
            accumulated_response = ""
            chunk_count = 0
            content_chunk_count = 0  # Track content chunks separately

            async for chunk in react_agent.astream(
                {"messages": messages},
                config={"callbacks": [ToolLoggingHandler()]},
                stream_mode="messages"
            ):
                chunk_count += 1
                # Chunk format with stream_mode="messages": (message, metadata)
                if len(chunk) == 2:
                    message, metadata = chunk

                    # Handle AIMessage (agent response or tool calls)
                    if isinstance(message, AIMessage):
                        # Check for tool calls first
                        if hasattr(message, 'tool_calls') and message.tool_calls and len(message.tool_calls) > 0:
                            # Tool invocation - yield friendly description for UI
                            for tool_call in message.tool_calls:
                                tool_name = tool_call.get("name", "")

                                # Skip empty tool names (streaming artifacts)
                                if not tool_name:
                                    continue

                                # Get friendly description from tool definition
                                tool_description = get_tool_description(tool_name, tools)

                                yield {
                                    "type": "tool_call",
                                    "tool": tool_name,  # Keep for logging/debugging
                                    "description": tool_description  # Use for customer-facing display
                                }
                        # Check for content (can have both tool_calls and content)
                        if message.content:
                            # Agent text response - yield token
                            content_chunk = message.content
                            accumulated_response += content_chunk
                            content_chunk_count += 1

                            yield {
                                "type": "token",
                                "content": content_chunk
                            }

                            # Progressive scanning every N chunks
                            from .config import Config
                            if content_chunk_count % Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL == 0 and Config.AIRS_ENABLED:
                                try:
                                    from .security.airs_scanner import scan_output, log_security_violation

                                    scan_result = await scan_output(
                                        response=accumulated_response,
                                        profile_name=Config.X_PAN_OUTPUT_CHECK_PROFILE_NAME
                                    )

                                    if scan_result.action == "block":
                                        # Log violation (stateless mode has no conversation_id)
                                        log_security_violation(
                                            scan_type="output",
                                            category=scan_result.category,
                                            action="block",
                                            profile_name=Config.X_PAN_OUTPUT_CHECK_PROFILE_NAME,
                                            content=accumulated_response,
                                            conversation_id=None,
                                            scan_context="progressive",
                                            chunks_accumulated=content_chunk_count
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

                    # Handle ToolMessage (tool results)
                    elif isinstance(message, ToolMessage):
                        yield {
                            "type": "tool_result",
                            "tool_call_id": message.tool_call_id,
                            "result": message.content
                        }

            # Final scan after streaming completes (per Decision 5)
            from .config import Config
            if Config.AIRS_ENABLED and accumulated_response:
                try:
                    from .security.airs_scanner import scan_output, log_security_violation

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
                            conversation_id=None,
                            scan_context="final",
                            chunks_accumulated=content_chunk_count
                        )

                        yield {
                            "type": "security_violation",
                            "message": "Response blocked due to content policy"
                        }
                        return

                except Exception as e:
                    logger.error(f"AIRS final scan failed: {e}")

            logger.debug(f"Stateless streaming complete: {accumulated_response}")
            logger.debug(f"Total chunks streamed: {chunk_count}")

        except Exception as e:
            logger.error(f"Error processing stateless streaming query: {e}")
            yield {
                "type": "error",
                "error": str(e)
            }


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