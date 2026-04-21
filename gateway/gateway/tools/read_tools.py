"""25 read-only NiFi MCP tools."""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging

from mcp.types import TextContent, Tool

from gateway.nifi.client import NiFiClient

log = logging.getLogger(__name__)
from gateway.tools.common import json_text, redact_sensitive
from gateway.tools.read_service import dispatch_read_tool
from gateway.nifi.flow_builder import analyze_flow_request
from gateway.nifi.setup_helper import SetupGuide
from gateway.nifi.best_practices import NiFiBestPractices


def _redact_sensitive(obj: Any, max_items: int = 200) -> Any:
    """Backward-compatible wrapper kept for existing tests/imports."""
    return redact_sensitive(obj, max_items)


def _json_text(data: Any) -> list[TextContent]:
    """Backward-compatible wrapper kept for existing tests/imports."""
    return json_text(data)


TOOLS: list[Tool] = [
    Tool(name="get_nifi_version", description="Get NiFi version and build information. Works with both NiFi 1.x and 2.x.", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_root_process_group", description="Return the root process group (read-only).", inputSchema={"type": "object", "properties": {}}),
    Tool(name="list_processors", description="List processors in a process group (read-only).", inputSchema={"type": "object", "properties": {"process_group_id": {"type": "string", "description": "Process group ID"}}, "required": ["process_group_id"]}),
    Tool(name="list_connections", description="List connections in a process group (read-only).", inputSchema={"type": "object", "properties": {"process_group_id": {"type": "string", "description": "Process group ID"}}, "required": ["process_group_id"]}),
    Tool(name="get_bulletins", description="Get recent bulletins/alerts (read-only).", inputSchema={"type": "object", "properties": {"after_ms": {"type": "integer", "description": "Only return bulletins after this timestamp (ms)"}}}),
    Tool(name="list_parameter_contexts", description="List all parameter contexts (read-only).", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_controller_services", description="Get controller services. If process_group_id is omitted, returns controller-level services.", inputSchema={"type": "object", "properties": {"process_group_id": {"type": "string", "description": "Process group ID (optional)"}}}),
    Tool(name="get_processor_types", description="Get all available processor types (read-only).", inputSchema={"type": "object", "properties": {}}),
    Tool(name="search_flow", description="Search the NiFi flow for components matching a query.", inputSchema={"type": "object", "properties": {"query": {"type": "string", "description": "Search query"}}, "required": ["query"]}),
    Tool(name="get_connection_details", description="Get details about a specific connection including queue size.", inputSchema={"type": "object", "properties": {"connection_id": {"type": "string", "description": "Connection ID"}}, "required": ["connection_id"]}),
    Tool(name="get_processor_details", description="Get detailed information about a specific processor.", inputSchema={"type": "object", "properties": {"processor_id": {"type": "string", "description": "Processor ID"}}, "required": ["processor_id"]}),
    Tool(name="list_input_ports", description="List input ports for a process group.", inputSchema={"type": "object", "properties": {"process_group_id": {"type": "string", "description": "Process group ID"}}, "required": ["process_group_id"]}),
    Tool(name="list_output_ports", description="List output ports for a process group.", inputSchema={"type": "object", "properties": {"process_group_id": {"type": "string", "description": "Process group ID"}}, "required": ["process_group_id"]}),
    Tool(name="get_processor_state", description="Get just the state of a processor (RUNNING, STOPPED, DISABLED).", inputSchema={"type": "object", "properties": {"processor_id": {"type": "string", "description": "Processor ID"}}, "required": ["processor_id"]}),
    Tool(name="check_connection_queue", description="Check queue size for a connection (flowfile count and bytes).", inputSchema={"type": "object", "properties": {"connection_id": {"type": "string", "description": "Connection ID"}}, "required": ["connection_id"]}),
    Tool(name="get_flow_summary", description="Get summary statistics for a process group (processor counts, queue sizes).", inputSchema={"type": "object", "properties": {"process_group_id": {"type": "string", "description": "Process group ID"}}, "required": ["process_group_id"]}),
    Tool(name="get_flow_health_status", description="Get comprehensive health status: processors, services, queues, bulletins, overall assessment.", inputSchema={"type": "object", "properties": {"pg_id": {"type": "string", "description": "Process group ID"}}, "required": ["pg_id"]}),
    Tool(name="get_controller_service_details", description="Get detailed controller service information including properties and state.", inputSchema={"type": "object", "properties": {"service_id": {"type": "string", "description": "Service ID"}}, "required": ["service_id"]}),
    Tool(name="find_controller_services_by_type", description="Find controller services by type to check if they already exist. Use BEFORE creating to avoid conflicts.", inputSchema={"type": "object", "properties": {"process_group_id": {"type": "string", "description": "Process group ID (use 'root' for controller-level)"}, "service_type": {"type": "string", "description": "Full service type name"}}, "required": ["process_group_id", "service_type"]}),
    Tool(name="get_parameter_context_details", description="Get parameter context with all parameters.", inputSchema={"type": "object", "properties": {"context_id": {"type": "string", "description": "Parameter context ID"}}, "required": ["context_id"]}),
    Tool(name="analyze_flow_build_request", description="Analyze a user's request to build a NiFi flow and provide guidance. Use BEFORE creating processors for complex flows.", inputSchema={"type": "object", "properties": {"user_request": {"type": "string", "description": "Description of the flow to build"}}, "required": ["user_request"]}),
    Tool(name="get_setup_instructions", description="Get comprehensive setup instructions for NiFi MCP Server configuration.", inputSchema={"type": "object", "properties": {}}),
    Tool(name="check_configuration", description="Check current NiFi MCP Server configuration and validate it.", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_best_practices_guide", description="Get NiFi flow building best practices guide.", inputSchema={"type": "object", "properties": {}}),
    Tool(name="get_recommended_workflow", description="Get recommended step-by-step workflow for building a specific flow.", inputSchema={"type": "object", "properties": {"user_request": {"type": "string", "description": "Description of the flow to build"}}, "required": ["user_request"]}),
]


async def handle(name: str, arguments: dict, client: NiFiClient) -> list[TextContent]:
    try:
        result = await dispatch_read_tool(
            name,
            arguments,
            client,
            analyze_flow_fn=analyze_flow_request,
            setup_guide_cls=SetupGuide,
            best_practices_cls=NiFiBestPractices,
        )
        if result.kind == "text":
            return [TextContent(type="text", text=str(result.payload))]
        payload = _redact_sensitive(result.payload) if result.redact else result.payload
        return _json_text(payload)
    except Exception:
        log.exception("Read tool %s failed", name)
        return [TextContent(type="text", text="Error: read operation failed")]
