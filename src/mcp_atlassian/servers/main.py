import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal, Optional
import time
import json

# CRITICAL: Configure logging BEFORE any FastMCP imports to ensure early patch logs are captured
# This must be done at the very beginning of the file
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("mcp-atlassian.server.main")

# CRITICAL: Patch MCP session validation to allow tools/list during initialization
# The error "Received request before initialization was complete" comes from mcp/server/session.py
try:
    # Import necessary FastMCP components
    from mcp.server.session import ServerSession
    from mcp.server.session import InitializationState
    from mcp.server.streamable_http import StreamableHTTPServerTransport
    # Any is required for type hints in patched functions - ensure it's available early
    from typing import Any, Callable
    import inspect # Imported here to avoid circular dependencies if used too early

    logger.info("Initializing FastMCP session validation bypass patches...")

    # --- Patch ServerSession._received_request (Handles initialization state bypass) ---
    original_received_request = ServerSession._received_request
        
    async def patched_received_request(self, responder: Any) -> None:
        """PATCHED: Always allow all requests - no session/UUID validation."""
        if self._initialization_state != InitializationState.Initialized:
            logger.info("MONKEY-PATCH: ServerSession._received_request - Marking session as initialized (validation disabled)")
            self._initialization_state = InitializationState.Initialized
        await original_received_request(self, responder)
    
    ServerSession._received_request = patched_received_request
    logger.info("✓ Successfully patched MCP ServerSession._received_request to allow tools/list during initialization")
        
    # --- Patch StreamableHTTPServerTransport (Handles direct request validation) ---

    # 1. Patch __init__ to automatically patch validation methods on ALL new instances
    original_init = StreamableHTTPServerTransport.__init__
    
    def patched_init(self, *args: Any, **kwargs: Any) -> None:
        """PATCHED: Patched __init__ to automatically patch validation methods on ALL new instances."""
        original_init(self, *args, **kwargs) # Call original __init__ first
        
        # Immediately patch this instance's validation methods
        patched_instance_methods = 0
        for method_name, log_desc in [
            ('_validate_session', '_validate_session'),
            ('_validate_request_headers', '_validate_request_headers'),
            ('_validate_protocol_version', '_validate_protocol_version'),
        ]:
            if hasattr(self, method_name):
                async def bypass_instance_method(request: Any, send: Any, name=log_desc) -> bool:
                    logger.info(f"MONKEY-PATCH-INIT: {name} called - BYPASSING (returning True)")
                    return True
                setattr(self, method_name, bypass_instance_method)
                patched_instance_methods += 1
                logger.debug(f"✓ Patched new instance {method_name} in __init__")

        if hasattr(self, '_handle_post_request'):
            original_handle_post = self._handle_post_request
            async def instance_handle_post_request(scope: Any, request: Any, receive: Any, send: Any) -> None:
                logger.info("MONKEY-PATCH-INIT: _handle_post_request called - validation should be bypassed")
                original_send = send
                async def patched_send(message: dict) -> None:
                    if message.get("type") == "http.response.start" and message.get("status") == 400:
                        logger.error(f"MONKEY-PATCH-INIT: FastMCP returning 400! Status: {message.get('status')}, Headers: {message.get('headers', {})}")
                    await original_send(message)
                try:
                    await original_handle_post(scope, request, receive, patched_send)
                except Exception as e:
                    logger.error(f"MONKEY-PATCH-INIT: Exception in _handle_post_request: {e}")
                    raise
            self._handle_post_request = instance_handle_post_request
            patched_instance_methods += 1
            logger.debug("✓ Patched new instance _handle_post_request in __init__")

        if patched_instance_methods > 0:
            logger.info(f"✓ Successfully applied {patched_instance_methods} instance-level patches in __init__")
    
    StreamableHTTPServerTransport.__init__ = patched_init
    logger.info("✓ Successfully patched StreamableHTTPServerTransport.__init__ to auto-patch all instances")
    
    # 2. ALSO patch class-level methods as backup (in case __init__ patch fails or for existing instances)
    patched_class_methods = 0
    
    # Define generic bypass function for class level
    async def bypass_class_method(self, *args: Any, **kwargs: Any) -> bool:
        method_name = inspect.currentframe().f_back.f_code.co_name if inspect else "unknown_method"
        logger.info(f"MONKEY-PATCH-CLASS: {method_name} called - BYPASSING (returning True)")
        return True

    for method_name in ['_validate_session', '_validate_request_headers', '_validate_protocol_version']:
        if hasattr(StreamableHTTPServerTransport, method_name):
            setattr(StreamableHTTPServerTransport, method_name, bypass_class_method)
            patched_class_methods += 1
            logger.info(f"✓ Patched StreamableHTTPServerTransport.{method_name} (class-level backup)")

    if hasattr(StreamableHTTPServerTransport, '_handle_post_request'):
        original_handle_post_request = StreamableHTTPServerTransport._handle_post_request
        async def class_patched_handle_post_request(self, scope: Any, request: Any, receive: Any, send: Any) -> None:
            logger.info("MONKEY-PATCH-CLASS: _handle_post_request called - validation should be bypassed")
            original_send = send
            async def patched_send(message: dict) -> None:
                if message.get("type") == "http.response.start" and message.get("status") == 400:
                    logger.error(f"MONKEY-PATCH-CLASS: FastMCP returning 400! Status: {message.get('status')}, Headers: {message.get('headers', {})}")
                await original_send(message)
            try:
                await original_handle_post_request(self, scope, request, receive, patched_send)
            except Exception as e:
                logger.error(f"MONKEY-PATCH-CLASS: Exception in _handle_post_request: {e}")
                raise
        StreamableHTTPServerTransport._handle_post_request = class_patched_handle_post_request
        patched_class_methods += 1
        logger.info("✓ Patched StreamableHTTPServerTransport._handle_post_request (class-level backup)")

    logger.info(f"✓ Successfully applied {patched_class_methods} class-level backup patches to StreamableHTTPServerTransport")
        
except Exception as e:
    logger.critical(f"FATAL ERROR: Failed to apply ALL critical FastMCP patches: {e}")
    import traceback
    logger.critical(f"FATAL ERROR: Traceback: {traceback.format_exc()}")
    raise # Re-raise to prevent server from starting unpatched


from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse


# --- Middleware Definitions ---

class LifespanContextMiddleware(BaseHTTPMiddleware):
    """Middleware to inject the lifespan context into each request's state."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> JSONResponse:
        # Access the global context that was set during lifespan startup
        import sys
        current_module = sys.modules[__name__]
        app_lifespan_context = getattr(current_module, '_pre_init_lifespan_context', {}).get("app_lifespan_context")

        if app_lifespan_context:
            request.state.app_lifespan_context = app_lifespan_context
        else:
            logger.warning("Lifespan context not found in middleware - this might indicate an issue with app startup.")

        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log incoming requests and detailed error responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID", "N/A")
        logger.info(f"Incoming Request - ID: {request_id}, Method: {request.method}, URL: {request.url.path}")

        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        if response.status_code >= 400:
            response_body = "(body not available for logging)"
            try:
                # Attempt to read body for error logging, but only if it's an error
                if hasattr(response, 'body_iterator') and response.status_code != 404: # Avoid reading 404 body
                    body_chunks = []
                    async for chunk in response.body_iterator:
                        body_chunks.append(chunk)
                    response_body = b''.join(body_chunks).decode('utf-8', errors='ignore')
                    response = JSONResponse(content=json.loads(response_body), status_code=response.status_code)
            except Exception as e:
                logger.warning(f"Failed to read response body for logging: {e}")

            logger.error(f"Request Error - ID: {request_id}, Method: {request.method}, URL: {request.url.path}, Status: {response.status_code}, Time: {process_time:.4f}s, Response: {mask_sensitive(response_body)}")
        else:
            logger.info(f"Request Complete - ID: {request_id}, Method: {request.method}, URL: {request.url.path}, Status: {response.status_code}, Time: {process_time:.4f}s")

        return response


class FastMCPValidationBypassMiddleware(BaseHTTPMiddleware):
    """Middleware to explicitly log if FastMCP validation still occurs, for debugging."""
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        response = await call_next(request)
        if response.status_code == 400:
            error_text = "Unable to read error body"
            try:
                body_chunks = []
                async for chunk in response.body_iterator:
                    body_chunks.append(chunk)
                body_bytes = b''.join(body_chunks)
                error_text = body_bytes.decode('utf-8', errors='ignore')
                
                # Always log 400 errors with full details
                logger.critical(f"CLOUD_RUN_DEBUG: 400 Bad Request on {request.url.path}")
                logger.critical(f"CLOUD_RUN_DEBUG: Method: {request.method}, Headers: {dict(request.headers)}")
                logger.critical(f"CLOUD_RUN_DEBUG: FastMCP 400 Error Response Body: {error_text}")
                
                if "No valid session ID" in error_text or "session ID" in error_text.lower():
                    logger.critical(f"BYPASS-MIDDLEWARE-FAILURE: FastMCP is still returning 400 with session validation message! Error: {error_text[:500]}")
                
                # Try to recreate response as JSON if possible
                try:
                    response = JSONResponse(content=json.loads(error_text), status_code=response.status_code)
                except (json.JSONDecodeError, ValueError):
                    logger.critical(f"CLOUD_RUN_DEBUG: 400 Error is not JSON, raw text: {error_text[:500]}")
                    # Return a plain text response
                    from starlette.responses import Response
                    response = Response(content=error_text, status_code=400, media_type="text/plain")
            except Exception as e:
                logger.critical(f"CLOUD_RUN_DEBUG: Failed to read 400 error body: {e}")
                logger.critical(f"CLOUD_RUN_DEBUG: Response type: {type(response)}, has body_iterator: {hasattr(response, 'body_iterator')}")
        return response


from cachetools import TTLCache
from fastmcp import FastMCP
from fastmcp.tools import Tool as FastMCPTool
from mcp.types import Tool as MCPTool
from mcp_atlassian.jira import JiraFetcher
from mcp_atlassian.jira.config import JiraConfig
from mcp_atlassian.utils.environment import get_available_services
from mcp_atlassian.utils.io import is_read_only_mode
from mcp_atlassian.utils.logging import mask_sensitive
from mcp_atlassian.utils.tools import get_enabled_tools, should_include_tool

from .context import MainAppContext
from .jira import jira_mcp


async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for Cloud Run and Kubernetes probes."""
    return JSONResponse({"status": "ok", "service": "mcp-atlassian-server"})


@asynccontextmanager
async def main_lifespan(app: FastMCP[MainAppContext]) -> AsyncIterator[dict]:
    """Lifespan manager - MUST yield context IMMEDIATELY before any async operations."""
    logger.info("Main Atlassian MCP server lifespan starting...")
    
    # Get Jira config if available
    jira_config = None
    if get_available_services().get("jira"):
        try:
            jira_config = JiraConfig.from_env()
            if not jira_config.is_auth_configured():
                jira_config = None
        except Exception as e:
            logger.warning(f"Failed to load Jira config in lifespan: {e}")
    
    # SessionManager removed - FastMCP handles sessions internally
    # No custom session management needed

    # Create context with correct field names
    context = MainAppContext(
        full_jira_config=jira_config,
        full_confluence_config=None,
        read_only=is_read_only_mode(),
        enabled_tools=get_enabled_tools(),
    )
    
    # Store in module for middleware access
    import sys
    sys.modules[__name__]._pre_init_lifespan_context = {"app_lifespan_context": context}

    yield {"app_lifespan_context": context}
    logger.info("Main Atlassian MCP server lifespan ending...")
    # Cleanup - SessionManager removed, no cleanup needed


# Configure FastMCP server
# Middleware order is important: RequestLoggingMiddleware should be outermost
middleware_list = [
    Middleware(LifespanContextMiddleware),
    Middleware(RequestLoggingMiddleware),
    Middleware(FastMCPValidationBypassMiddleware), # This middleware is kept for debugging if patches fail
]

# NOTE: FastMCP.__init__ is where the http_app method is created, which in turn
# creates the StreamableHTTPServerTransport instance. Our patches at module-level
# will affect this instance creation.

# Create the main FastMCP instance
main_mcp = FastMCP[
    MainAppContext
](
    name="Atlassian MCP",
    lifespan=main_lifespan,
)

# Mount jira_mcp to register all Jira tools
main_mcp.mount("jira", jira_mcp)
logger.info("Mounted Jira tools.")

# Expose the ASGI app for Gunicorn/Uvicorn
app = main_mcp.http_app(
    path="/mcp",
    middleware=middleware_list,
)

# AtlassianMCP.http_app should not re-define context_type/lifespan/tools/middleware
# It uses the FastMCP instance's own configured properties
# The context passed to http_app is for the ASGI app lifetime, not FastMCP lifespan context

# Final check of patches after everything is loaded
import inspect
if hasattr(StreamableHTTPServerTransport, '__init__') and 'patched_init' in inspect.getsource(StreamableHTTPServerTransport.__init__):
    logger.info("CONFIRMATION: StreamableHTTPServerTransport.__init__ shows patch in source.")
else:
    logger.warning("CONFIRMATION: StreamableHTTPServerTransport.__init__ does NOT show patch in source.")

if hasattr(ServerSession, '_received_request') and 'patched_received_request' in inspect.getsource(ServerSession._received_request):
    logger.info("CONFIRMATION: ServerSession._received_request shows patch in source.")
else:
    logger.warning("CONFIRMATION: ServerSession._received_request does NOT show patch in source.")

logger.info("FastMCP server setup complete.")
