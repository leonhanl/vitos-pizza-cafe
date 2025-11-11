"""Callback handlers for LangChain tool and agent execution logging."""

import logging
from typing import Any, Dict, Optional
from uuid import UUID
from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)


class ToolLoggingHandler(BaseCallbackHandler):
    """Callback handler for logging tool invocations with full request/response details.

    This handler logs all tool calls (both MCP and database tools) at INFO level,
    including complete input parameters and output responses.
    """

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        inputs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Log when a tool execution starts.

        Args:
            serialized: Tool metadata including name and description
            input_str: String representation of tool input
            run_id: Unique identifier for this tool run
            parent_run_id: ID of the parent run (agent)
            inputs: Dictionary of input parameters
            **kwargs: Additional keyword arguments
        """
        tool_name = serialized.get("name", "unknown")

        # Log tool invocation with full input details
        logger.info(f"🔧 [Tool Call] {tool_name}")
        logger.info(f"   Input: {input_str}")
        if inputs:
            logger.info(f"   Parameters: {inputs}")

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> Any:
        """Log when a tool execution completes successfully.

        Args:
            output: The tool's output/response
            run_id: Unique identifier for this tool run
            parent_run_id: ID of the parent run (agent)
            **kwargs: Additional keyword arguments
        """
        # Log tool response with full output
        logger.info(f"✅ [Tool Response]")
        logger.info(f"   Output: {output}")

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> Any:
        """Log when a tool execution fails.

        Args:
            error: The exception that occurred
            run_id: Unique identifier for this tool run
            parent_run_id: ID of the parent run (agent)
            **kwargs: Additional keyword arguments
        """
        logger.error(f"❌ [Tool Error] {type(error).__name__}: {error}")
