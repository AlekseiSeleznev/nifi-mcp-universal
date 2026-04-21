"""35 write NiFi MCP tools (require readonly=false on the connection)."""

from __future__ import annotations

from typing import Any

import logging

from mcp.types import TextContent, Tool

from gateway.nifi.client import NiFiClient

log = logging.getLogger(__name__)
from gateway.nifi.best_practices import SmartFlowBuilder
from gateway.tools.common import json_text, redact_sensitive
from gateway.tools.write_service import dispatch_write_tool


def _redact_sensitive(obj: Any, max_items: int = 200) -> Any:
    return redact_sensitive(obj, max_items)


def _json_text(data: Any) -> list[TextContent]:
    return json_text(data)


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
        data = await dispatch_write_tool(name, arguments, client, builder_cls=SmartFlowBuilder)
        if data is None:
            return _json_text({"error": f"Unknown write tool: {name}"})
        return _json_text(_redact_sensitive(data))
    except Exception:
        log.exception("Write tool %s failed", name)
        return [TextContent(type="text", text="Error: write operation failed")]
