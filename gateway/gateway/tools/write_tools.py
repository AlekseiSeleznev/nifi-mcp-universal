"""42 write NiFi MCP tools (require readonly=false on the connection)."""

from __future__ import annotations

import json
from typing import Any

import logging

import anyio
from mcp.types import TextContent, Tool

from gateway.nifi.client import NiFiClient

log = logging.getLogger(__name__)
from gateway.nifi.best_practices import SmartFlowBuilder


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


# --- Tool definitions ---

TOOLS: list[Tool] = [
    # Processor lifecycle
    Tool(name="start_processor", description="Start a processor. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"processor_id": {"type": "string"}, "version": {"type": "integer"}}, "required": ["processor_id", "version"]}),
    Tool(name="stop_processor", description="Stop a processor. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"processor_id": {"type": "string"}, "version": {"type": "integer"}}, "required": ["processor_id", "version"]}),
    Tool(name="create_processor", description="Create a new processor. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"process_group_id": {"type": "string"}, "processor_type": {"type": "string", "description": "Fully qualified type (e.g. org.apache.nifi.processors.standard.LogAttribute)"}, "name": {"type": "string"}, "position_x": {"type": "number", "default": 0}, "position_y": {"type": "number", "default": 0}}, "required": ["process_group_id", "processor_type", "name"]}),
    Tool(name="update_processor_config", description="Update processor configuration. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"processor_id": {"type": "string"}, "version": {"type": "integer"}, "config": {"type": "object", "description": "Configuration with properties, scheduling, etc."}}, "required": ["processor_id", "version", "config"]}),
    Tool(name="delete_processor", description="Delete a processor. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"processor_id": {"type": "string"}, "version": {"type": "integer"}}, "required": ["processor_id", "version"]}),
    Tool(name="terminate_processor", description="Forcefully terminate a stuck processor. Last resort. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"processor_id": {"type": "string"}, "version": {"type": "integer"}}, "required": ["processor_id", "version"]}),
    Tool(name="start_all_processors_in_group", description="Start ALL processors in a process group (bulk). WRITE OPERATION.", inputSchema={"type": "object", "properties": {"pg_id": {"type": "string"}}, "required": ["pg_id"]}),
    Tool(name="stop_all_processors_in_group", description="Stop ALL processors in a process group (bulk). WRITE OPERATION.", inputSchema={"type": "object", "properties": {"pg_id": {"type": "string"}}, "required": ["pg_id"]}),

    # Connections
    Tool(name="create_connection", description="Create a connection between two components. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"process_group_id": {"type": "string"}, "source_id": {"type": "string"}, "source_type": {"type": "string", "description": "PROCESSOR, INPUT_PORT, OUTPUT_PORT, FUNNEL"}, "destination_id": {"type": "string"}, "destination_type": {"type": "string"}, "relationships": {"type": "string", "description": "Comma-separated list (e.g. 'success,failure')"}}, "required": ["process_group_id", "source_id", "source_type", "destination_id", "destination_type", "relationships"]}),
    Tool(name="delete_connection", description="Delete a connection (queue must be empty). WRITE OPERATION.", inputSchema={"type": "object", "properties": {"connection_id": {"type": "string"}, "version": {"type": "integer"}}, "required": ["connection_id", "version"]}),
    Tool(name="empty_connection_queue", description="Drop all flowfiles from a connection queue. WARNING: irreversible. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"connection_id": {"type": "string"}}, "required": ["connection_id"]}),

    # Controller services
    Tool(name="create_controller_service", description="Create a controller service. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"process_group_id": {"type": "string"}, "service_type": {"type": "string", "description": "Fully qualified service type"}, "name": {"type": "string"}}, "required": ["process_group_id", "service_type", "name"]}),
    Tool(name="update_controller_service_properties", description="Update controller service properties (must be DISABLED). WRITE OPERATION.", inputSchema={"type": "object", "properties": {"service_id": {"type": "string"}, "version": {"type": "integer"}, "properties": {"type": "object", "description": "Key-value properties"}}, "required": ["service_id", "version", "properties"]}),
    Tool(name="enable_controller_service", description="Enable a controller service. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"service_id": {"type": "string"}, "version": {"type": "integer"}}, "required": ["service_id", "version"]}),
    Tool(name="disable_controller_service", description="Disable a controller service. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"service_id": {"type": "string"}, "version": {"type": "integer"}}, "required": ["service_id", "version"]}),
    Tool(name="delete_controller_service", description="Delete a controller service (must be DISABLED and unreferenced). WRITE OPERATION.", inputSchema={"type": "object", "properties": {"service_id": {"type": "string"}, "version": {"type": "integer"}}, "required": ["service_id", "version"]}),
    Tool(name="enable_all_controller_services_in_group", description="Enable ALL controller services in a process group (bulk). WRITE OPERATION.", inputSchema={"type": "object", "properties": {"pg_id": {"type": "string"}}, "required": ["pg_id"]}),

    # Process groups
    Tool(name="start_new_flow", description="Create a new process group following best practices. RECOMMENDED way to start building flows. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"flow_name": {"type": "string", "description": "Descriptive flow name"}, "parent_pg_id": {"type": "string", "description": "Parent process group (defaults to root)"}}, "required": ["flow_name"]}),
    Tool(name="create_process_group", description="Create a process group for organizing flows. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"parent_id": {"type": "string"}, "name": {"type": "string"}, "position_x": {"type": "number", "default": 0}, "position_y": {"type": "number", "default": 0}}, "required": ["parent_id", "name"]}),
    Tool(name="update_process_group_name", description="Rename a process group. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"pg_id": {"type": "string"}, "version": {"type": "integer"}, "name": {"type": "string"}}, "required": ["pg_id", "version", "name"]}),
    Tool(name="delete_process_group", description="Delete a process group (must be empty). WRITE OPERATION.", inputSchema={"type": "object", "properties": {"pg_id": {"type": "string"}, "version": {"type": "integer"}}, "required": ["pg_id", "version"]}),

    # Ports
    Tool(name="create_input_port", description="Create an input port. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"pg_id": {"type": "string"}, "name": {"type": "string"}, "position_x": {"type": "number", "default": 0}, "position_y": {"type": "number", "default": 0}}, "required": ["pg_id", "name"]}),
    Tool(name="create_output_port", description="Create an output port. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"pg_id": {"type": "string"}, "name": {"type": "string"}, "position_x": {"type": "number", "default": 0}, "position_y": {"type": "number", "default": 0}}, "required": ["pg_id", "name"]}),
    Tool(name="update_input_port", description="Rename an input port. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"port_id": {"type": "string"}, "version": {"type": "integer"}, "name": {"type": "string"}}, "required": ["port_id", "version", "name"]}),
    Tool(name="update_output_port", description="Rename an output port. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"port_id": {"type": "string"}, "version": {"type": "integer"}, "name": {"type": "string"}}, "required": ["port_id", "version", "name"]}),
    Tool(name="delete_input_port", description="Delete an input port. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"port_id": {"type": "string"}, "version": {"type": "integer"}}, "required": ["port_id", "version"]}),
    Tool(name="delete_output_port", description="Delete an output port. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"port_id": {"type": "string"}, "version": {"type": "integer"}}, "required": ["port_id", "version"]}),
    Tool(name="start_input_port", description="Start an input port. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"port_id": {"type": "string"}, "version": {"type": "integer"}}, "required": ["port_id", "version"]}),
    Tool(name="stop_input_port", description="Stop an input port. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"port_id": {"type": "string"}, "version": {"type": "integer"}}, "required": ["port_id", "version"]}),
    Tool(name="start_output_port", description="Start an output port. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"port_id": {"type": "string"}, "version": {"type": "integer"}}, "required": ["port_id", "version"]}),
    Tool(name="stop_output_port", description="Stop an output port. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"port_id": {"type": "string"}, "version": {"type": "integer"}}, "required": ["port_id", "version"]}),

    # Parameter contexts
    Tool(name="create_parameter_context", description="Create a parameter context. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string", "default": ""}, "parameters": {"type": "string", "description": "JSON array: [{\"name\":\"key\",\"value\":\"val\",\"sensitive\":false}]", "default": "[]"}}, "required": ["name"]}),
    Tool(name="update_parameter_context", description="Update parameter context. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"context_id": {"type": "string"}, "version": {"type": "integer"}, "name": {"type": "string"}, "parameters": {"type": "string", "description": "JSON array of parameters"}}, "required": ["context_id", "version"]}),
    Tool(name="delete_parameter_context", description="Delete a parameter context (must not be referenced). WRITE OPERATION.", inputSchema={"type": "object", "properties": {"context_id": {"type": "string"}, "version": {"type": "integer"}}, "required": ["context_id", "version"]}),
    Tool(name="apply_parameter_context_to_process_group", description="Apply a parameter context to a process group. WRITE OPERATION.", inputSchema={"type": "object", "properties": {"pg_id": {"type": "string"}, "pg_version": {"type": "integer"}, "context_id": {"type": "string"}}, "required": ["pg_id", "pg_version", "context_id"]}),
]


async def handle(name: str, arguments: dict, client: NiFiClient, readonly: bool) -> list[TextContent]:
    if readonly:
        return [TextContent(type="text", text=f"Error: Connection is in read-only mode. Set readonly=false when connecting to enable write operations. Tool: '{name}'")]

    try:
        # Processor lifecycle
        if name == "start_processor":
            data = await anyio.to_thread.run_sync(lambda: client.start_processor(arguments["processor_id"], arguments["version"]))
            return _json_text(_redact_sensitive(data))
        if name == "stop_processor":
            data = await anyio.to_thread.run_sync(lambda: client.stop_processor(arguments["processor_id"], arguments["version"]))
            return _json_text(_redact_sensitive(data))
        if name == "create_processor":
            data = await anyio.to_thread.run_sync(lambda: client.create_processor(arguments["process_group_id"], arguments["processor_type"], arguments["name"], arguments.get("position_x", 0), arguments.get("position_y", 0)))
            return _json_text(_redact_sensitive(data))
        if name == "update_processor_config":
            data = await anyio.to_thread.run_sync(lambda: client.update_processor(arguments["processor_id"], arguments["version"], arguments["config"]))
            return _json_text(_redact_sensitive(data))
        if name == "delete_processor":
            data = await anyio.to_thread.run_sync(lambda: client.delete_processor(arguments["processor_id"], arguments["version"]))
            return _json_text(_redact_sensitive(data))
        if name == "terminate_processor":
            data = await anyio.to_thread.run_sync(lambda: client.terminate_processor(arguments["processor_id"], arguments["version"]))
            return _json_text(_redact_sensitive(data))
        if name == "start_all_processors_in_group":
            data = await anyio.to_thread.run_sync(lambda: client.start_all_processors_in_group(arguments["pg_id"]))
            return _json_text(_redact_sensitive(data))
        if name == "stop_all_processors_in_group":
            data = await anyio.to_thread.run_sync(lambda: client.stop_all_processors_in_group(arguments["pg_id"]))
            return _json_text(_redact_sensitive(data))

        # Connections
        if name == "create_connection":
            rel_list = [r.strip() for r in arguments["relationships"].split(",")]
            data = await anyio.to_thread.run_sync(lambda: client.create_connection(arguments["process_group_id"], arguments["source_id"], arguments["source_type"], arguments["destination_id"], arguments["destination_type"], rel_list))
            return _json_text(_redact_sensitive(data))
        if name == "delete_connection":
            data = await anyio.to_thread.run_sync(lambda: client.delete_connection(arguments["connection_id"], arguments["version"]))
            return _json_text(_redact_sensitive(data))
        if name == "empty_connection_queue":
            data = await anyio.to_thread.run_sync(lambda: client.empty_connection_queue(arguments["connection_id"]))
            return _json_text(_redact_sensitive(data))

        # Controller services
        if name == "create_controller_service":
            data = await anyio.to_thread.run_sync(lambda: client.create_controller_service(arguments["process_group_id"], arguments["service_type"], arguments["name"]))
            return _json_text(_redact_sensitive(data))
        if name == "update_controller_service_properties":
            data = await anyio.to_thread.run_sync(lambda: client.update_controller_service(arguments["service_id"], arguments["version"], arguments["properties"]))
            return _json_text(_redact_sensitive(data))
        if name == "enable_controller_service":
            data = await anyio.to_thread.run_sync(lambda: client.enable_controller_service(arguments["service_id"], arguments["version"]))
            return _json_text(_redact_sensitive(data))
        if name == "disable_controller_service":
            data = await anyio.to_thread.run_sync(lambda: client.disable_controller_service(arguments["service_id"], arguments["version"]))
            return _json_text(_redact_sensitive(data))
        if name == "delete_controller_service":
            data = await anyio.to_thread.run_sync(lambda: client.delete_controller_service(arguments["service_id"], arguments["version"]))
            return _json_text(_redact_sensitive(data))
        if name == "enable_all_controller_services_in_group":
            data = await anyio.to_thread.run_sync(lambda: client.enable_all_controller_services_in_group(arguments["pg_id"]))
            return _json_text(_redact_sensitive(data))

        # Process groups
        if name == "start_new_flow":
            builder = SmartFlowBuilder(client)
            data = await anyio.to_thread.run_sync(lambda: builder.start_new_flow(arguments["flow_name"], arguments.get("parent_pg_id")))
            return _json_text(_redact_sensitive(data))
        if name == "create_process_group":
            data = await anyio.to_thread.run_sync(lambda: client.create_process_group(arguments["parent_id"], arguments["name"], arguments.get("position_x", 0), arguments.get("position_y", 0)))
            return _json_text(_redact_sensitive(data))
        if name == "update_process_group_name":
            data = await anyio.to_thread.run_sync(lambda: client.update_process_group(arguments["pg_id"], arguments["version"], arguments["name"]))
            return _json_text(_redact_sensitive(data))
        if name == "delete_process_group":
            data = await anyio.to_thread.run_sync(lambda: client.delete_process_group(arguments["pg_id"], arguments["version"]))
            return _json_text(_redact_sensitive(data))

        # Ports
        if name == "create_input_port":
            data = await anyio.to_thread.run_sync(lambda: client.create_input_port(arguments["pg_id"], arguments["name"], arguments.get("position_x", 0), arguments.get("position_y", 0)))
            return _json_text(_redact_sensitive(data))
        if name == "create_output_port":
            data = await anyio.to_thread.run_sync(lambda: client.create_output_port(arguments["pg_id"], arguments["name"], arguments.get("position_x", 0), arguments.get("position_y", 0)))
            return _json_text(_redact_sensitive(data))
        if name == "update_input_port":
            data = await anyio.to_thread.run_sync(lambda: client.update_input_port(arguments["port_id"], arguments["version"], arguments["name"]))
            return _json_text(_redact_sensitive(data))
        if name == "update_output_port":
            data = await anyio.to_thread.run_sync(lambda: client.update_output_port(arguments["port_id"], arguments["version"], arguments["name"]))
            return _json_text(_redact_sensitive(data))
        if name == "delete_input_port":
            data = await anyio.to_thread.run_sync(lambda: client.delete_input_port(arguments["port_id"], arguments["version"]))
            return _json_text(_redact_sensitive(data))
        if name == "delete_output_port":
            data = await anyio.to_thread.run_sync(lambda: client.delete_output_port(arguments["port_id"], arguments["version"]))
            return _json_text(_redact_sensitive(data))
        if name == "start_input_port":
            data = await anyio.to_thread.run_sync(lambda: client.start_input_port(arguments["port_id"], arguments["version"]))
            return _json_text(_redact_sensitive(data))
        if name == "stop_input_port":
            data = await anyio.to_thread.run_sync(lambda: client.stop_input_port(arguments["port_id"], arguments["version"]))
            return _json_text(_redact_sensitive(data))
        if name == "start_output_port":
            data = await anyio.to_thread.run_sync(lambda: client.start_output_port(arguments["port_id"], arguments["version"]))
            return _json_text(_redact_sensitive(data))
        if name == "stop_output_port":
            data = await anyio.to_thread.run_sync(lambda: client.stop_output_port(arguments["port_id"], arguments["version"]))
            return _json_text(_redact_sensitive(data))

        # Parameter contexts
        if name == "create_parameter_context":
            params_list = json.loads(arguments.get("parameters", "[]")) or None
            data = await anyio.to_thread.run_sync(lambda: client.create_parameter_context(arguments["name"], arguments.get("description", ""), params_list))
            return _json_text(_redact_sensitive(data))
        if name == "update_parameter_context":
            params_list = json.loads(arguments["parameters"]) if arguments.get("parameters") else None
            data = await anyio.to_thread.run_sync(lambda: client.update_parameter_context(arguments["context_id"], arguments["version"], arguments.get("name"), None, params_list))
            return _json_text(_redact_sensitive(data))
        if name == "delete_parameter_context":
            data = await anyio.to_thread.run_sync(lambda: client.delete_parameter_context(arguments["context_id"], arguments["version"]))
            return _json_text(_redact_sensitive(data))
        if name == "apply_parameter_context_to_process_group":
            data = await anyio.to_thread.run_sync(lambda: client.apply_parameter_context_to_process_group(arguments["pg_id"], arguments["pg_version"], arguments["context_id"]))
            return _json_text(_redact_sensitive(data))

        return _json_text({"error": f"Unknown write tool: {name}"})
    except Exception as e:
        log.exception("Write tool %s failed", name)
        return [TextContent(type="text", text=f"Error: {e}")]
