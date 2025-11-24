"""
AIRS (AI Runtime Security) Scanner Module

Provides decorator-based prompt scanning using Palo Alto Networks Prisma AIRS.
Uses decorator pattern for minimal code intrusion and clean separation of concerns.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache, wraps
from typing import Callable, Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Result from AIRS security scan"""
    action: str  # "allow" or "block"
    category: Optional[str] = None
    details: Optional[dict] = None


@lru_cache(maxsize=1)
def get_scanner():
    """
    Initialize and return AIRS Scanner singleton.
    Uses lru_cache to ensure single instance across application lifecycle.

    Returns:
        Scanner instance or None if AIRS not enabled/configured
    """
    try:
        import aisecurity
        from aisecurity.scan.asyncio.scanner import Scanner
        from backend.config import Config

        if not Config.AIRS_ENABLED:
            logger.info("AIRS scanning is disabled (AIRS_ENABLED=false)")
            return None

        if not Config.X_PAN_TOKEN:
            logger.warning("AIRS enabled but X_PAN_TOKEN not configured, disabling scanner")
            return None

        # Initialize SDK with API key
        aisecurity.init(api_key=Config.X_PAN_TOKEN)
        scanner = Scanner()
        logger.info("AIRS Scanner initialized successfully")
        return scanner

    except ImportError as e:
        logger.error(f"Failed to import AIRS SDK: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize AIRS Scanner: {e}")
        return None


async def scan_input(prompt: str, profile_name: str) -> ScanResult:
    """
    Scan user input for security threats.

    Args:
        prompt: User input text to scan
        profile_name: AIRS profile name for input validation

    Returns:
        ScanResult with action (allow/block) and details
    """
    scanner = get_scanner()
    if not scanner:
        # Scanner not initialized, allow by default (fail-open for availability)
        return ScanResult(action="allow")

    try:
        from aisecurity.generated_openapi_client.models.ai_profile import AiProfile
        from aisecurity.scan.models.content import Content

        ai_profile = AiProfile(profile_name=profile_name)
        scan_response = await scanner.sync_scan(
            ai_profile=ai_profile,
            content=Content(prompt=prompt)
        )

        action = scan_response.action if hasattr(scan_response, 'action') else "allow"
        category = scan_response.category if hasattr(scan_response, 'category') else None

        logger.info(f"Input scan result: action={action}, category={category}")

        return ScanResult(
            action=action,
            category=category,
            details={"profile": profile_name, "scan_type": "input"}
        )

    except Exception as e:
        logger.error(f"AIRS input scan failed: {e}", exc_info=True)
        # Fail-open: allow request to proceed if scanner fails
        return ScanResult(action="allow")


async def scan_output(response: str, profile_name: str) -> ScanResult:
    """
    Scan AI response for security issues (data leakage, toxic content, etc.).

    Args:
        response: AI-generated response text to scan
        profile_name: AIRS profile name for output validation

    Returns:
        ScanResult with action (allow/block) and details
    """
    scanner = get_scanner()
    if not scanner:
        # Scanner not initialized, allow by default
        return ScanResult(action="allow")

    try:
        from aisecurity.generated_openapi_client.models.ai_profile import AiProfile
        from aisecurity.scan.models.content import Content

        ai_profile = AiProfile(profile_name=profile_name)
        scan_response = await scanner.sync_scan(
            ai_profile=ai_profile,
            content=Content(response=response)
        )

        action = scan_response.action if hasattr(scan_response, 'action') else "allow"
        category = scan_response.category if hasattr(scan_response, 'category') else None

        logger.info(f"Output scan result: action={action}, category={category}")

        return ScanResult(
            action=action,
            category=category,
            details={"profile": profile_name, "scan_type": "output"}
        )

    except Exception as e:
        logger.error(f"AIRS output scan failed: {e}", exc_info=True)
        # Fail-open: allow response to proceed if scanner fails
        return ScanResult(action="allow")


def log_security_violation(
    scan_type: str,
    category: str,
    action: str,
    profile_name: str,
    content: str,
    conversation_id: Optional[str] = None
) -> None:
    """
    Log detailed security violation information for monitoring and audit.

    This function logs all security-relevant details that are NOT shown to users,
    maintaining a full audit trail for security teams while protecting the
    security configuration from being exposed to potential attackers.

    Args:
        scan_type: Type of scan ("input" or "output")
        category: AIRS violation category (e.g., "malicious", "pii", "toxic")
        action: Action taken ("block" or "allow")
        profile_name: AIRS profile name used for scanning
        content: The actual content that was blocked (prompt or response)
        conversation_id: Optional conversation identifier for tracking
    """
    logger.warning(
        f"AIRS Security Violation - "
        f"scan_type={scan_type}, "
        f"category={category}, "
        f"action={action}, "
        f"profile={profile_name}, "
        f"conversation_id={conversation_id}, "
        f"content={content}"  # Log full content for audit
    )


def scan_with_airs(func: Callable) -> Callable:
    """
    Decorator to add AIRS security scanning to FastAPI endpoints.

    Performs:
    1. Input scan before endpoint execution (checks user prompt)
    2. Output scan after endpoint execution (checks AI response)

    Raises HTTPException(403) if either scan blocks the request/response.

    Usage:
        @app.post("/api/v1/chat")
        @scan_with_airs
        async def chat(request: ChatRequest):
            ...
    """
    @wraps(func)
    async def wrapper(request, *args, **kwargs):
        from backend.config import Config

        # Skip scanning if AIRS not enabled
        if not Config.AIRS_ENABLED:
            return await func(request, *args, **kwargs)

        # Input scan - check user prompt before processing
        input_result = await scan_input(
            prompt=request.message,
            profile_name=Config.X_PAN_INPUT_CHECK_PROFILE_NAME
        )

        if input_result.action == "block":
            # Log detailed security violation for monitoring (NOT shown to user)
            log_security_violation(
                scan_type="input",
                category=input_result.category,
                action="block",
                profile_name=Config.X_PAN_INPUT_CHECK_PROFILE_NAME,
                content=request.message,
                conversation_id=getattr(request, 'conversation_id', None)
            )

            # Return sanitized error message to user (no security details)
            raise HTTPException(
                status_code=403,
                detail="Your request couldn't be processed due to our content policy. Please rephrase your message and try again."
            )

        # Execute original endpoint
        response = await func(request, *args, **kwargs)

        # Output scan - check AI response before returning
        output_result = await scan_output(
            response=response.response,
            profile_name=Config.X_PAN_OUTPUT_CHECK_PROFILE_NAME
        )

        if output_result.action == "block":
            # Log detailed security violation for monitoring (NOT shown to user)
            log_security_violation(
                scan_type="output",
                category=output_result.category,
                action="block",
                profile_name=Config.X_PAN_OUTPUT_CHECK_PROFILE_NAME,
                content=response.response,
                conversation_id=getattr(request, 'conversation_id', None)
            )

            # Return sanitized error message to user (no security details)
            raise HTTPException(
                status_code=403,
                detail="The response couldn't be displayed due to our content policy. Please try a different question."
            )

        return response

    return wrapper
