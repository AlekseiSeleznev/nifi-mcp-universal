"""Service-layer dispatch for write NiFi tools."""

from __future__ import annotations

import json

import anyio

from gateway.nifi.client import NiFiClient
from gateway.nifi.best_practices import SmartFlowBuilder


def _parse_relationships(value: str) -> list[str]:
    return [item for item in (part.strip() for part in value.split(",")) if item]


def _parse_parameters(raw: str | None) -> list[dict] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid parameters JSON. Expected a JSON array.") from exc
    if parsed in (None, []):
        return None
    if not isinstance(parsed, list):
        raise ValueError("Invalid parameters JSON. Expected a JSON array.")
    return parsed


async def _call_client(client: NiFiClient, method_name: str, *args):
    method = getattr(client, method_name)
    return await anyio.to_thread.run_sync(lambda: method(*args))


async def dispatch_write_tool(
    name: str,
    arguments: dict,
    client: NiFiClient,
    *,
    builder_cls=SmartFlowBuilder,
):
    # Processor lifecycle
    if name == "start_processor":
        return await _call_client(client, "start_processor", arguments["processor_id"], arguments["version"])
    if name == "stop_processor":
        return await _call_client(client, "stop_processor", arguments["processor_id"], arguments["version"])
    if name == "create_processor":
        return await _call_client(
            client,
            "create_processor",
            arguments["process_group_id"],
            arguments["processor_type"],
            arguments["name"],
            arguments.get("position_x", 0),
            arguments.get("position_y", 0),
        )
    if name == "update_processor_config":
        return await _call_client(client, "update_processor", arguments["processor_id"], arguments["version"], arguments["config"])
    if name == "delete_processor":
        return await _call_client(client, "delete_processor", arguments["processor_id"], arguments["version"])
    if name == "terminate_processor":
        return await _call_client(client, "terminate_processor", arguments["processor_id"], arguments["version"])
    if name == "start_all_processors_in_group":
        return await _call_client(client, "start_all_processors_in_group", arguments["pg_id"])
    if name == "stop_all_processors_in_group":
        return await _call_client(client, "stop_all_processors_in_group", arguments["pg_id"])

    # Connections
    if name == "create_connection":
        rel_list = _parse_relationships(arguments["relationships"])
        return await _call_client(
            client,
            "create_connection",
            arguments["process_group_id"],
            arguments["source_id"],
            arguments["source_type"],
            arguments["destination_id"],
            arguments["destination_type"],
            rel_list,
        )
    if name == "delete_connection":
        return await _call_client(client, "delete_connection", arguments["connection_id"], arguments["version"])
    if name == "empty_connection_queue":
        return await _call_client(client, "empty_connection_queue", arguments["connection_id"])

    # Controller services
    if name == "create_controller_service":
        return await _call_client(client, "create_controller_service", arguments["process_group_id"], arguments["service_type"], arguments["name"])
    if name == "update_controller_service_properties":
        return await _call_client(client, "update_controller_service", arguments["service_id"], arguments["version"], arguments["properties"])
    if name == "enable_controller_service":
        return await _call_client(client, "enable_controller_service", arguments["service_id"], arguments["version"])
    if name == "disable_controller_service":
        return await _call_client(client, "disable_controller_service", arguments["service_id"], arguments["version"])
    if name == "delete_controller_service":
        return await _call_client(client, "delete_controller_service", arguments["service_id"], arguments["version"])
    if name == "enable_all_controller_services_in_group":
        return await _call_client(client, "enable_all_controller_services_in_group", arguments["pg_id"])

    # Process groups
    if name == "start_new_flow":
        builder = builder_cls(client)
        return await anyio.to_thread.run_sync(lambda: builder.start_new_flow(arguments["flow_name"], arguments.get("parent_pg_id")))
    if name == "create_process_group":
        return await _call_client(
            client,
            "create_process_group",
            arguments["parent_id"],
            arguments["name"],
            arguments.get("position_x", 0),
            arguments.get("position_y", 0),
        )
    if name == "update_process_group_name":
        return await _call_client(client, "update_process_group", arguments["pg_id"], arguments["version"], arguments["name"])
    if name == "delete_process_group":
        return await _call_client(client, "delete_process_group", arguments["pg_id"], arguments["version"])

    # Ports
    if name == "create_input_port":
        return await _call_client(client, "create_input_port", arguments["pg_id"], arguments["name"], arguments.get("position_x", 0), arguments.get("position_y", 0))
    if name == "create_output_port":
        return await _call_client(client, "create_output_port", arguments["pg_id"], arguments["name"], arguments.get("position_x", 0), arguments.get("position_y", 0))
    if name == "update_input_port":
        return await _call_client(client, "update_input_port", arguments["port_id"], arguments["version"], arguments["name"])
    if name == "update_output_port":
        return await _call_client(client, "update_output_port", arguments["port_id"], arguments["version"], arguments["name"])
    if name == "delete_input_port":
        return await _call_client(client, "delete_input_port", arguments["port_id"], arguments["version"])
    if name == "delete_output_port":
        return await _call_client(client, "delete_output_port", arguments["port_id"], arguments["version"])
    if name == "start_input_port":
        return await _call_client(client, "start_input_port", arguments["port_id"], arguments["version"])
    if name == "stop_input_port":
        return await _call_client(client, "stop_input_port", arguments["port_id"], arguments["version"])
    if name == "start_output_port":
        return await _call_client(client, "start_output_port", arguments["port_id"], arguments["version"])
    if name == "stop_output_port":
        return await _call_client(client, "stop_output_port", arguments["port_id"], arguments["version"])

    # Parameter contexts
    if name == "create_parameter_context":
        params_list = _parse_parameters(arguments.get("parameters", "[]"))
        return await _call_client(client, "create_parameter_context", arguments["name"], arguments.get("description", ""), params_list)
    if name == "update_parameter_context":
        params_list = _parse_parameters(arguments.get("parameters"))
        return await _call_client(
            client,
            "update_parameter_context",
            arguments["context_id"],
            arguments["version"],
            arguments.get("name"),
            None,
            params_list,
        )
    if name == "delete_parameter_context":
        return await _call_client(client, "delete_parameter_context", arguments["context_id"], arguments["version"])
    if name == "apply_parameter_context_to_process_group":
        return await _call_client(client, "apply_parameter_context_to_process_group", arguments["pg_id"], arguments["pg_version"], arguments["context_id"])

    return None
