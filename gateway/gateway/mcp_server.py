"""MCP Server — tool registration and dispatch."""

from __future__ import annotations

import contextvars
import logging

from mcp.server import Server
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
    Tool,
)

from gateway.tools import admin, read_tools, write_tools
from gateway.nifi_client_manager import client_manager

log = logging.getLogger(__name__)

# Per-request context variable holding the Mcp-Session-Id header value.
# Set by server.py's handle_mcp() before forwarding each request to the
# transport, so tool handlers can retrieve it without touching MCP SDK internals.
_current_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_current_session_id", default=None
)


AGENT_INSTRUCTIONS = """
You are connected to **nifi-mcp-universal** — a gateway to Apache NiFi flow
control and inspection at http://localhost:8085/mcp. For ANY task related
to NiFi (inspect a flow, create/modify processors, diagnose queues, manage
controller services), **use these MCP tools first; do NOT guess endpoint
paths or processor property names from memory**.

Intent recognition — when the user's request is an Apache NiFi task,
route it here:
  User phrases that pin the session to this MCP:
    «NiFi / Apache NiFi / нифи», «используем NiFi <имя>»,
    «работаем с NiFi <имя>», «подключись к NiFi <имя>»,
    «в NiFi <имя>», «switch to NiFi <name>».
  NiFi-specific terminology (any of these → use THIS MCP):
    processor (в dataflow-контексте), process group / PG,
    controller service, flowfile, bulletin, relationship, queue backlog,
    parameter context, provenance, GetFile/PutFile/GenerateFlowFile/
    InvokeHTTP/ListenHTTP/ConsumeKafka (имена процессоров).
  Typical connection-name hints: prod-nifi, dev-nifi, <env>-nifi,
    nifi-<cluster>. NiFi URLs end in `/nifi-api` or port 8080/9443.
  Action when user names a NiFi («используем NiFi prod»):
    1) list_nifi_connections → if `prod` present, switch_nifi name=prod.
    2) If not present, ask the user for NiFi URL + auth and call
       connect_nifi (default readonly=true — safer).
  If the user says «X» without specifying NiFi, call
  list_nifi_connections here first; if X is present, proceed. If not,
  say so and ask — do NOT invent a connection.

Pre-flight (always):
  1. list_nifi_connections — confirm a NiFi instance is registered.
     If empty: ask the user for NiFi URL + auth method and call
     connect_nifi (readonly=true by default — safer).
  2. test_nifi_connection — before any heavy operation on a new host.
  3. get_root_process_group — every flow navigation starts here; cache
     the returned PG id for subsequent list_* calls.

Read / inspect flow:
  list_processors, list_connections, list_input_ports, list_output_ports,
  get_processor_details (capture `version` for later safe updates!),
  check_connection_queue, get_bulletins, get_flow_health_status,
  get_flow_summary, search_flow.

Before writing (readonly=false must be set on the connection):
  • Creating a processor: get_processor_types first, then create_processor.
  • Creating a controller service: find_controller_services_by_type first
    to avoid duplicates.
  • Updating a processor/controller-service: always fetch *_details first
    to get the current `version` (optimistic locking in NiFi API).
  • Designing a new flow from a user prompt: call
    analyze_flow_build_request first — it returns an AI-friendly
    design plan.

Dangerous (irreversible) operations — ALWAYS ask the user to confirm:
  empty_connection_queue, delete_processor, delete_connection,
  delete_controller_service, delete_process_group, delete_*_port,
  start_all_processors_in_group, stop_all_processors_in_group.

If a required connection is not registered or the NiFi backend is
unreachable, tell the user explicitly — do NOT silently fall back to
hand-crafted HTTP or invented answers. Use get_server_status to verify
gateway health when in doubt.

Common pitfalls — read this before calling unfamiliar tools:
  • Always inspect `tools/list` and read inputSchema before a first
    call. Do NOT invent argument names. Most tool-level errors are
    `'X' is a required property`.
  • NiFi API uses OPTIMISTIC LOCKING. Every write tool (update_*,
    delete_*, start_*, stop_*, enable_*, disable_*, terminate_*)
    takes a `version` field. Flow: fetch get_processor_details /
    get_controller_service_details / get_connection_details FIRST
    to read `version`, then pass it to the write call. On conflict
    (stale version), refetch details and retry ONCE. Never invent
    version numbers.
  • Before any list_* on a sub-tree, call get_root_process_group
    to obtain a real process_group_id. Most list/create tools take
    `process_group_id`; a minority (get_flow_health_status,
    start_all_processors_in_group, stop_all_processors_in_group,
    delete_process_group, *_port tools) take `pg_id` instead —
    they are NOT interchangeable. Read the schema before calling.
  • update_processor_config.config shape depends on the processor
    type — fetch get_processor_details first to learn the real
    property names. Do not guess property keys.
  • create_connection requires BOTH `source_type` and
    `destination_type` (PROCESSOR / INPUT_PORT / OUTPUT_PORT) AND
    the `relationships` array. Missing relationships → 400.
  • apply_parameter_context_to_process_group requires BOTH
    `pg_version` AND the latest `context_id` — get them freshly
    before calling.
  • readonly connections reject writes with 403. If the write tool
    errors out, check connection mode via list_nifi_connections and
    tell the user to reconnect with `readonly=false`.
  • Active registration is per Mcp-Session-Id. Call `switch_nifi`
    once per session. Two sessions can target different NiFi
    instances concurrently — they are isolated.
  • If a call returns HTTP 404 or the session stops responding, the
    gateway dropped the session. Re-initialize (initialize +
    notifications/initialized); do NOT retry on the same SID.
  • Before ANY destructive op (empty_connection_queue, delete_*,
    start_all_processors_in_group, stop_all_processors_in_group,
    enable_all_controller_services_in_group) show the full plan —
    list of ids/names — and wait for an explicit "yes".
""".strip()


server = Server("nifi-mcp-universal", instructions=AGENT_INSTRUCTIONS)

ALL_TOOL_MODULES = [admin, read_tools, write_tools]

_TOOL_DISPATCH: dict[str, object] = {}
for _mod in ALL_TOOL_MODULES:
    for _tool in _mod.TOOLS:
        _TOOL_DISPATCH[_tool.name] = _mod


def _error_result(message: str) -> CallToolResult:
    """Return an MCP error result with isError=True per the MCP specification."""
    return CallToolResult(
        isError=True,
        content=[TextContent(type="text", text=message)],
    )


@server.list_tools()
async def list_tools() -> list[Tool]:
    tools = []
    for mod in ALL_TOOL_MODULES:
        tools.extend(mod.TOOLS)
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent] | CallToolResult:
    # Extract session ID from MCP request context
    session_id = _get_session_id()

    mod = _TOOL_DISPATCH.get(name)
    if not mod:
        return _error_result(f"Unknown tool: {name}")

    try:
        if mod is admin:
            return await admin.handle(name, arguments, session_id)

        # For NiFi tools, resolve client from session
        client = client_manager.get_client(session_id)
        conn_info = client_manager.get_connection_info(session_id)

        if mod is read_tools:
            return await read_tools.handle(name, arguments, client)

        if mod is write_tools:
            readonly = conn_info.readonly if conn_info else True
            return await write_tools.handle(name, arguments, client, readonly)

    except Exception:
        log.exception("Tool %s failed", name)
        return _error_result("Error: tool execution failed")

    return _error_result(f"Unhandled tool: {name}")


def _get_session_id() -> str | None:
    """Return the Mcp-Session-Id for the current request.

    The value is injected by server.py's handle_mcp() via _current_session_id
    ContextVar before the request is forwarded to the MCP transport.  When
    called outside an HTTP request (e.g. from tests or stdio transport) the
    ContextVar default of None is returned, which causes the client_manager to
    fall back to the global active connection.
    """
    return _current_session_id.get()


# ---------------------------------------------------------------------------
# MCP Prompts — ready-to-run playbooks for typical NiFi tasks
# ---------------------------------------------------------------------------

_PROMPTS: list[tuple[Prompt, str]] = [
    (
        Prompt(
            name="connect_and_inspect",
            description=(
                "Connect (or reuse) a NiFi registration, then show a quick "
                "overview: root PG, processor count, bulletins, health."
            ),
            arguments=[],
        ),
        (
            "Use nifi-mcp-universal to: "
            "1) list_nifi_connections. If empty, ask the user for NiFi URL "
            "and auth; call connect_nifi with readonly=true. "
            "2) test_nifi_connection. "
            "3) get_root_process_group → capture PG id. "
            "4) list_processors, list_connections in that PG. "
            "5) get_flow_health_status + get_bulletins. "
            "Summarise. Never invent processor names or endpoint paths."
        ),
    ),
    (
        Prompt(
            name="diagnose_flow_health",
            description=(
                "Find what is wrong with a flow: bulletins, queue backlog, "
                "stopped processors, failing controller services."
            ),
            arguments=[],
        ),
        (
            "Flow-health triage: "
            "1) get_flow_health_status. "
            "2) get_bulletins — recent alerts/warnings. "
            "3) For each non-empty queue: check_connection_queue. "
            "4) get_controller_services → find DISABLED / INVALID ones. "
            "5) list_processors → flag any stopped/invalid nodes. "
            "Produce a prioritised list of issues with the exact tool calls "
            "that produced each finding. No guesses."
        ),
    ),
    (
        Prompt(
            name="build_flow_from_request",
            description=(
                "Design a new NiFi flow based on a user requirement. Analyses "
                "intent, suggests processor types, emits a step-by-step "
                "creation script."
            ),
            arguments=[
                PromptArgument(
                    name="request",
                    description="What the flow should do (user's words).",
                    required=True,
                ),
            ],
        ),
        (
            "Design a flow for: {request}\n"
            "1) analyze_flow_build_request with the request. "
            "2) get_processor_types to see what is installed. "
            "3) For each planned processor, find matching type in the list. "
            "4) For controller services, find_controller_services_by_type "
            "first to avoid duplicates. "
            "5) Output a sequence of create_process_group / "
            "create_processor / create_controller_service / "
            "create_connection calls. Do NOT execute them yet — show the "
            "plan to the user and ask to confirm readonly=false is set."
        ),
    ),
    (
        Prompt(
            name="safe_processor_update",
            description=(
                "Safely update a processor's configuration — fetches current "
                "version first (NiFi API optimistic locking)."
            ),
            arguments=[
                PromptArgument(
                    name="processor_id",
                    description="NiFi processor UUID",
                    required=True,
                ),
            ],
        ),
        (
            "Update processor {processor_id}: "
            "1) get_processor_details — capture current `version` and full "
            "config. "
            "2) Describe the proposed diff in plain text to the user. "
            "3) On confirmation: call update_processor_config with the "
            "version from step 1. If the call fails with conflict, refetch "
            "and retry once. Never skip step 1."
        ),
    ),
    (
        Prompt(
            name="stop_all_safely",
            description=(
                "Stop every processor in a process group — irreversible for "
                "running state; requires explicit user confirmation."
            ),
            arguments=[
                PromptArgument(
                    name="pg_id",
                    description="Process group id",
                    required=True,
                ),
            ],
        ),
        (
            "Bulk stop on PG {pg_id}: "
            "1) list_processors in the group → show the user what will stop "
            "(id, name, current state). "
            "2) Ask the user to confirm explicitly. "
            "3) Only on \"yes\" call stop_all_processors_in_group. "
            "4) Verify with get_flow_health_status."
        ),
    ),
]


@server.list_prompts()
async def list_prompts() -> list[Prompt]:
    return [p for p, _ in _PROMPTS]


@server.get_prompt()
async def get_prompt(name: str, arguments: dict | None = None) -> GetPromptResult:
    for prompt, body in _PROMPTS:
        if prompt.name == name:
            args = arguments or {}
            try:
                text = body.format(**args)
            except KeyError:
                text = body
            return GetPromptResult(
                description=prompt.description,
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(type="text", text=text),
                    )
                ],
            )
    raise ValueError(f"Unknown prompt: {name}")
