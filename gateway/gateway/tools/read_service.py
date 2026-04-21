"""Service-layer dispatch for read-only NiFi tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import anyio

from gateway.nifi.client import NiFiClient
from gateway.nifi.flow_builder import analyze_flow_request
from gateway.nifi.best_practices import NiFiBestPractices
from gateway.nifi.setup_helper import SetupGuide


@dataclass(frozen=True)
class ReadDispatchResult:
    kind: str  # "json" | "text"
    payload: Any
    redact: bool = False


async def _call_client(client: NiFiClient, method_name: str, *args):
    method = getattr(client, method_name)
    return await anyio.to_thread.run_sync(lambda: method(*args))


async def dispatch_read_tool(
    name: str,
    arguments: dict,
    client: NiFiClient,
    *,
    analyze_flow_fn=analyze_flow_request,
    setup_guide_cls=SetupGuide,
    best_practices_cls=NiFiBestPractices,
) -> ReadDispatchResult:
    if name == "get_nifi_version":
        data = await _call_client(client, "get_version_info")
        version_tuple = await _call_client(client, "get_version_tuple")
        is_2x = await _call_client(client, "is_nifi_2x")
        return ReadDispatchResult(
            kind="json",
            payload={
                "version_info": data,
                "parsed_version": f"{version_tuple[0]}.{version_tuple[1]}.{version_tuple[2]}",
                "is_nifi_2x": is_2x,
            },
            redact=True,
        )

    if name == "get_root_process_group":
        return ReadDispatchResult("json", await _call_client(client, "get_root_process_group"), redact=True)

    if name == "list_processors":
        return ReadDispatchResult("json", await _call_client(client, "list_processors", arguments["process_group_id"]), redact=True)

    if name == "list_connections":
        return ReadDispatchResult("json", await _call_client(client, "list_connections", arguments["process_group_id"]), redact=True)

    if name == "get_bulletins":
        return ReadDispatchResult("json", await _call_client(client, "get_bulletins", arguments.get("after_ms")), redact=True)

    if name == "list_parameter_contexts":
        return ReadDispatchResult("json", await _call_client(client, "list_parameter_contexts"), redact=True)

    if name == "get_controller_services":
        return ReadDispatchResult("json", await _call_client(client, "get_controller_services", arguments.get("process_group_id")), redact=True)

    if name == "get_processor_types":
        return ReadDispatchResult("json", await _call_client(client, "get_processor_types"), redact=True)

    if name == "search_flow":
        return ReadDispatchResult("json", await _call_client(client, "search_flow", arguments["query"]), redact=True)

    if name == "get_connection_details":
        return ReadDispatchResult("json", await _call_client(client, "get_connection", arguments["connection_id"]), redact=True)

    if name == "get_processor_details":
        return ReadDispatchResult("json", await _call_client(client, "get_processor", arguments["processor_id"]), redact=True)

    if name == "list_input_ports":
        return ReadDispatchResult("json", await _call_client(client, "get_input_ports", arguments["process_group_id"]), redact=True)

    if name == "list_output_ports":
        return ReadDispatchResult("json", await _call_client(client, "get_output_ports", arguments["process_group_id"]), redact=True)

    if name == "get_processor_state":
        state = await _call_client(client, "get_processor_state", arguments["processor_id"])
        return ReadDispatchResult("json", {"state": state})

    if name == "check_connection_queue":
        return ReadDispatchResult("json", await _call_client(client, "get_connection_queue_size", arguments["connection_id"]))

    if name == "get_flow_summary":
        return ReadDispatchResult("json", await _call_client(client, "get_process_group_summary", arguments["process_group_id"]))

    if name == "get_flow_health_status":
        return ReadDispatchResult("json", await _call_client(client, "get_flow_health_status", arguments["pg_id"]), redact=True)

    if name == "get_controller_service_details":
        return ReadDispatchResult("json", await _call_client(client, "get_controller_service", arguments["service_id"]), redact=True)

    if name == "find_controller_services_by_type":
        pg_id = arguments["process_group_id"]
        resolved_pg_id = None if pg_id.lower() == "root" else pg_id
        matches = await _call_client(client, "find_controller_services_by_type", resolved_pg_id, arguments["service_type"])
        simplified = [
            {
                "id": s.get("component", {}).get("id"),
                "name": s.get("component", {}).get("name"),
                "type": s.get("component", {}).get("type"),
                "state": s.get("component", {}).get("state"),
                "version": s.get("revision", {}).get("version"),
            }
            for s in matches
        ]
        return ReadDispatchResult("json", {"count": len(simplified), "services": simplified})

    if name == "get_parameter_context_details":
        return ReadDispatchResult("json", await _call_client(client, "get_parameter_context", arguments["context_id"]), redact=True)

    if name == "analyze_flow_build_request":
        return ReadDispatchResult("json", analyze_flow_fn(arguments["user_request"]))

    if name == "get_setup_instructions":
        return ReadDispatchResult("text", setup_guide_cls.get_setup_instructions())

    if name == "check_configuration":
        is_valid, errors, warnings = setup_guide_cls.validate_current_config()
        return ReadDispatchResult("json", {"is_valid": is_valid, "errors": errors, "warnings": warnings})

    if name == "get_best_practices_guide":
        return ReadDispatchResult("text", best_practices_cls.get_best_practices_guide())

    if name == "get_recommended_workflow":
        return ReadDispatchResult("text", best_practices_cls.get_recommended_workflow_for_request(arguments["user_request"]))

    return ReadDispatchResult("json", {"error": f"Unknown read tool: {name}"})
