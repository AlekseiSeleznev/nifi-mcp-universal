"""24 read-only NiFi MCP tools."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import logging

import anyio
from mcp.types import TextContent, Tool

from gateway.nifi.client import NiFiClient

log = logging.getLogger(__name__)
from gateway.nifi.flow_builder import analyze_flow_request
from gateway.nifi.best_practices import NiFiBestPractices
from gateway.nifi.setup_helper import SetupGuide


def _redact_sensitive(obj: Any, max_items: int = 200) -> Any:
    # All keys stored lowercase for case-insensitive comparison
    _REDACT_KEYS = {"password", "passcode", "token", "secret", "kerberoskeytab", "sslkeystorepasswd"}
    if isinstance(obj, dict):
        return {k: ("***REDACTED***" if k.lower() in _REDACT_KEYS else _redact_sensitive(v, max_items)) for k, v in obj.items()}
    if isinstance(obj, list):
        if len(obj) > max_items:
            return [_redact_sensitive(x, max_items) for x in obj[:max_items]] + [{"truncated": True, "omitted_count": len(obj) - max_items}]
        return [_redact_sensitive(x, max_items) for x in obj]
    return obj


def _json_text(data: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False, default=str))]


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
        if name == "get_nifi_version":
            data = await anyio.to_thread.run_sync(client.get_version_info)
            version_tuple = await anyio.to_thread.run_sync(client.get_version_tuple)
            is_2x = await anyio.to_thread.run_sync(client.is_nifi_2x)
            return _json_text({"version_info": _redact_sensitive(data), "parsed_version": f"{version_tuple[0]}.{version_tuple[1]}.{version_tuple[2]}", "is_nifi_2x": is_2x})

        if name == "get_root_process_group":
            data = await anyio.to_thread.run_sync(client.get_root_process_group)
            return _json_text(_redact_sensitive(data))

        if name == "list_processors":
            data = await anyio.to_thread.run_sync(lambda: client.list_processors(arguments["process_group_id"]))
            return _json_text(_redact_sensitive(data))

        if name == "list_connections":
            data = await anyio.to_thread.run_sync(lambda: client.list_connections(arguments["process_group_id"]))
            return _json_text(_redact_sensitive(data))

        if name == "get_bulletins":
            after_ms = arguments.get("after_ms")
            data = await anyio.to_thread.run_sync(lambda: client.get_bulletins(after_ms))
            return _json_text(_redact_sensitive(data))

        if name == "list_parameter_contexts":
            data = await anyio.to_thread.run_sync(client.list_parameter_contexts)
            return _json_text(_redact_sensitive(data))

        if name == "get_controller_services":
            pg_id = arguments.get("process_group_id")
            data = await anyio.to_thread.run_sync(lambda: client.get_controller_services(pg_id))
            return _json_text(_redact_sensitive(data))

        if name == "get_processor_types":
            data = await anyio.to_thread.run_sync(client.get_processor_types)
            return _json_text(_redact_sensitive(data))

        if name == "search_flow":
            data = await anyio.to_thread.run_sync(lambda: client.search_flow(arguments["query"]))
            return _json_text(_redact_sensitive(data))

        if name == "get_connection_details":
            data = await anyio.to_thread.run_sync(lambda: client.get_connection(arguments["connection_id"]))
            return _json_text(_redact_sensitive(data))

        if name == "get_processor_details":
            data = await anyio.to_thread.run_sync(lambda: client.get_processor(arguments["processor_id"]))
            return _json_text(_redact_sensitive(data))

        if name == "list_input_ports":
            data = await anyio.to_thread.run_sync(lambda: client.get_input_ports(arguments["process_group_id"]))
            return _json_text(_redact_sensitive(data))

        if name == "list_output_ports":
            data = await anyio.to_thread.run_sync(lambda: client.get_output_ports(arguments["process_group_id"]))
            return _json_text(_redact_sensitive(data))

        if name == "get_processor_state":
            data = await anyio.to_thread.run_sync(lambda: client.get_processor_state(arguments["processor_id"]))
            return _json_text({"state": data})

        if name == "check_connection_queue":
            data = await anyio.to_thread.run_sync(lambda: client.get_connection_queue_size(arguments["connection_id"]))
            return _json_text(data)

        if name == "get_flow_summary":
            data = await anyio.to_thread.run_sync(lambda: client.get_process_group_summary(arguments["process_group_id"]))
            return _json_text(data)

        if name == "get_flow_health_status":
            data = await anyio.to_thread.run_sync(lambda: client.get_flow_health_status(arguments["pg_id"]))
            return _json_text(_redact_sensitive(data))

        if name == "get_controller_service_details":
            data = await anyio.to_thread.run_sync(lambda: client.get_controller_service(arguments["service_id"]))
            return _json_text(_redact_sensitive(data))

        if name == "find_controller_services_by_type":
            pg_id = arguments["process_group_id"]
            pg_id = None if pg_id.lower() == "root" else pg_id
            matches = await anyio.to_thread.run_sync(lambda: client.find_controller_services_by_type(pg_id, arguments["service_type"]))
            simplified = [{"id": s.get("component", {}).get("id"), "name": s.get("component", {}).get("name"), "type": s.get("component", {}).get("type"), "state": s.get("component", {}).get("state"), "version": s.get("revision", {}).get("version")} for s in matches]
            return _json_text({"count": len(simplified), "services": simplified})

        if name == "get_parameter_context_details":
            data = await anyio.to_thread.run_sync(lambda: client.get_parameter_context(arguments["context_id"]))
            return _json_text(_redact_sensitive(data))

        if name == "analyze_flow_build_request":
            data = analyze_flow_request(arguments["user_request"])
            return _json_text(data)

        if name == "get_setup_instructions":
            return [TextContent(type="text", text=SetupGuide.get_setup_instructions())]

        if name == "check_configuration":
            is_valid, errors, warnings = SetupGuide.validate_current_config()
            return _json_text({"is_valid": is_valid, "errors": errors, "warnings": warnings})

        if name == "get_best_practices_guide":
            return [TextContent(type="text", text=NiFiBestPractices.get_best_practices_guide())]

        if name == "get_recommended_workflow":
            return [TextContent(type="text", text=NiFiBestPractices.get_recommended_workflow_for_request(arguments["user_request"]))]

        return _json_text({"error": f"Unknown read tool: {name}"})
    except Exception as e:
        log.exception("Read tool %s failed", name)
        return [TextContent(type="text", text=f"Error: {e}")]
