# MCP Tool Catalog

Total tools: **66**.

Generated from `gateway/gateway/mcp_server.py` tool modules.
Regenerate with: `python3 tools/generate_tool_catalog.py`.

## `admin` (6)

| Tool | Description |
|------|-------------|
| `connect_nifi` | Register and connect to a NiFi instance. Provide name, url, auth_method and credentials. |
| `disconnect_nifi` | Disconnect and remove a NiFi connection by name. |
| `get_server_status` | Get MCP gateway status: active connections, sessions, default. |
| `list_nifi_connections` | List all registered NiFi connections with their status. |
| `switch_nifi` | Switch the active NiFi connection for the current session. |
| `test_nifi_connection` | Test connectivity to a NiFi instance without saving. |

## `read_tools` (25)

| Tool | Description |
|------|-------------|
| `analyze_flow_build_request` | Analyze a user's request to build a NiFi flow and provide guidance. Use BEFORE creating processors for complex flows. |
| `check_configuration` | Check current NiFi MCP Server configuration and validate it. |
| `check_connection_queue` | Check queue size for a connection (flowfile count and bytes). |
| `find_controller_services_by_type` | Find controller services by type to check if they already exist. Use BEFORE creating to avoid conflicts. |
| `get_best_practices_guide` | Get NiFi flow building best practices guide. |
| `get_bulletins` | Get recent bulletins/alerts (read-only). |
| `get_connection_details` | Get details about a specific connection including queue size. |
| `get_controller_service_details` | Get detailed controller service information including properties and state. |
| `get_controller_services` | Get controller services. If process_group_id is omitted, returns controller-level services. |
| `get_flow_health_status` | Get comprehensive health status: processors, services, queues, bulletins, overall assessment. |
| `get_flow_summary` | Get summary statistics for a process group (processor counts, queue sizes). |
| `get_nifi_version` | Get NiFi version and build information. Works with both NiFi 1.x and 2.x. |
| `get_parameter_context_details` | Get parameter context with all parameters. |
| `get_processor_details` | Get detailed information about a specific processor. |
| `get_processor_state` | Get just the state of a processor (RUNNING, STOPPED, DISABLED). |
| `get_processor_types` | Get all available processor types (read-only). |
| `get_recommended_workflow` | Get recommended step-by-step workflow for building a specific flow. |
| `get_root_process_group` | Return the root process group (read-only). |
| `get_setup_instructions` | Get comprehensive setup instructions for NiFi MCP Server configuration. |
| `list_connections` | List connections in a process group (read-only). |
| `list_input_ports` | List input ports for a process group. |
| `list_output_ports` | List output ports for a process group. |
| `list_parameter_contexts` | List all parameter contexts (read-only). |
| `list_processors` | List processors in a process group (read-only). |
| `search_flow` | Search the NiFi flow for components matching a query. |

## `write_tools` (35)

| Tool | Description |
|------|-------------|
| `apply_parameter_context_to_process_group` | Apply a parameter context to a process group. WRITE OPERATION. |
| `create_connection` | Create a connection between two components. WRITE OPERATION. |
| `create_controller_service` | Create a controller service. WRITE OPERATION. |
| `create_input_port` | Create an input port. WRITE OPERATION. |
| `create_output_port` | Create an output port. WRITE OPERATION. |
| `create_parameter_context` | Create a parameter context. WRITE OPERATION. |
| `create_process_group` | Create a process group for organizing flows. WRITE OPERATION. |
| `create_processor` | Create a new processor. WRITE OPERATION. |
| `delete_connection` | Delete a connection (queue must be empty). WRITE OPERATION. |
| `delete_controller_service` | Delete a controller service (must be DISABLED and unreferenced). WRITE OPERATION. |
| `delete_input_port` | Delete an input port. WRITE OPERATION. |
| `delete_output_port` | Delete an output port. WRITE OPERATION. |
| `delete_parameter_context` | Delete a parameter context (must not be referenced). WRITE OPERATION. |
| `delete_process_group` | Delete a process group (must be empty). WRITE OPERATION. |
| `delete_processor` | Delete a processor. WRITE OPERATION. |
| `disable_controller_service` | Disable a controller service. WRITE OPERATION. |
| `empty_connection_queue` | Drop all flowfiles from a connection queue. WARNING: irreversible. WRITE OPERATION. |
| `enable_all_controller_services_in_group` | Enable ALL controller services in a process group (bulk). WRITE OPERATION. |
| `enable_controller_service` | Enable a controller service. WRITE OPERATION. |
| `start_all_processors_in_group` | Start ALL processors in a process group (bulk). WRITE OPERATION. |
| `start_input_port` | Start an input port. WRITE OPERATION. |
| `start_new_flow` | Create a new process group following best practices. RECOMMENDED way to start building flows. WRITE OPERATION. |
| `start_output_port` | Start an output port. WRITE OPERATION. |
| `start_processor` | Start a processor. WRITE OPERATION. |
| `stop_all_processors_in_group` | Stop ALL processors in a process group (bulk). WRITE OPERATION. |
| `stop_input_port` | Stop an input port. WRITE OPERATION. |
| `stop_output_port` | Stop an output port. WRITE OPERATION. |
| `stop_processor` | Stop a processor. WRITE OPERATION. |
| `terminate_processor` | Forcefully terminate a stuck processor. Last resort. WRITE OPERATION. |
| `update_controller_service_properties` | Update controller service properties (must be DISABLED). WRITE OPERATION. |
| `update_input_port` | Rename an input port. WRITE OPERATION. |
| `update_output_port` | Rename an output port. WRITE OPERATION. |
| `update_parameter_context` | Update parameter context. WRITE OPERATION. |
| `update_process_group_name` | Rename a process group. WRITE OPERATION. |
| `update_processor_config` | Update processor configuration. WRITE OPERATION. |
