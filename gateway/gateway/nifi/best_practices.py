"""
Best practices helper for NiFi flow building.

This module enforces NiFi best practices and provides intelligent defaults.
"""

from typing import Dict, Any, Optional, Tuple, List
import re


class NiFiBestPractices:
    """Helper class for enforcing NiFi best practices."""
    
    @staticmethod
    def should_create_process_group_for_flow(flow_description: str) -> Tuple[bool, str]:
        """
        Determine if a flow should be created in a new process group.
        
        Best Practice: Always create flows in process groups, not on root canvas.
        
        Args:
            flow_description: Description of the flow being built
            
        Returns:
            Tuple of (should_create_pg, suggested_pg_name)
        """
        # Always recommend creating a process group for organization
        should_create = True
        
        # Try to extract a meaningful name from the description
        suggested_name = NiFiBestPractices._suggest_process_group_name(flow_description)
        
        return should_create, suggested_name
    
    @staticmethod
    def _suggest_process_group_name(description: str) -> str:
        """
        Suggest a process group name based on flow description.
        
        Args:
            description: Flow description
            
        Returns:
            Suggested process group name
        """
        description_lower = description.lower()
        
        # Common patterns
        if "etl" in description_lower or "extract" in description_lower and "transform" in description_lower:
            return "ETL Pipeline"
        elif "ingest" in description_lower or "ingestion" in description_lower:
            return "Data Ingestion"
        elif "sql" in description_lower or "database" in description_lower or "db" in description_lower:
            return "Database Integration"
        elif "kafka" in description_lower:
            return "Kafka Pipeline"
        elif "s3" in description_lower or "storage" in description_lower:
            return "Storage Integration"
        elif "api" in description_lower or "rest" in description_lower:
            return "API Integration"
        elif "file" in description_lower:
            return "File Processing"
        elif "iceberg" in description_lower:
            return "Iceberg Integration"
        else:
            # Generic name
            return "Flow Pipeline"
    
    @staticmethod
    def get_best_practices_guide() -> str:
        """Get comprehensive best practices guide."""
        return """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                     NiFi Flow Building - Best Practices                      ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

🏗️ PROCESS GROUP ORGANIZATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ DO: Always create flows inside process groups
   - Keeps canvas organized
   - Easier to manage and understand
   - Supports modularity and reusability
   - Enables parameter contexts per group

❌ DON'T: Build directly on root canvas
   - Gets messy quickly
   - Hard to manage multiple flows
   - No logical organization

Example:
  Root Canvas
  ├─ Process Group: "Data Ingestion"
  │   ├─ FetchS3
  │   ├─ ParseCSV
  │   └─ ValidateData
  ├─ Process Group: "Transformation"
  │   ├─ ConvertRecord
  │   └─ TransformData
  └─ Process Group: "Output"
      └─ PutDatabaseRecord

📁 NAMING CONVENTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Process Groups:
  ✅ "Data Ingestion" - Descriptive, clear purpose
  ✅ "ETL Pipeline" - Well-known pattern
  ✅ "Kafka to S3" - Clear data flow
  ❌ "Group1" - Generic, not descriptive
  ❌ "test" - Not production-appropriate

Processors:
  ✅ "Fetch Customer Data from S3" - Specific purpose
  ✅ "Parse CSV Records" - Clear action
  ❌ "Processor1" - Generic
  ❌ "test" - Not descriptive

🔄 FLOW LIFECYCLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Correct order for building flows:

1. Create Process Group
   create_process_group(root_id, "Data Ingestion Pipeline")

2. Create Controller Services (if needed)
   create_controller_service(pg_id, "DBCPConnectionPool", "MySQL Connection")

3. Enable Controller Services
   enable_controller_service(service_id, version)

4. Create Processors
   create_processor(pg_id, "org.apache.nifi.processors...", "Processor Name")

5. Configure Processors
   update_processor_config(processor_id, version, properties={...})

6. Create Connections
   create_connection(pg_id, source_id, dest_id, ["success"])

7. Start Processors
   start_all_processors_in_group(pg_id)  # Or start individually

⚙️ CONTROLLER SERVICES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ DO: Create services at appropriate scope
   - Process group level for shared resources
   - Enable before starting processors

❌ DON'T: Create duplicate services
   - One DBCPConnectionPool per database
   - Reuse services across processors

🔗 CONNECTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ DO: Handle all relationships
   - success → next processor
   - failure → log and route
   - retry → loop back or DLQ

❌ DON'T: Leave unhandled relationships
   - Auto-terminates by default
   - May lose data unexpectedly

📊 PARAMETERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ DO: Use parameter contexts for environment-specific config
   - Database connection strings
   - API endpoints
   - File paths
   - Credentials (mark as sensitive)

Example:
  1. Create context: create_parameter_context("Production DB", [...])
  2. Apply to group: apply_parameter_context_to_process_group(pg_id, context_id)
  3. Reference in processors: #{db.host}, #{db.password}

🏃 STARTING FLOWS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Correct startup sequence:

1. Enable all controller services first
   enable_all_controller_services_in_group(pg_id)

2. Start processors
   start_all_processors_in_group(pg_id)  # Bulk operation (fast!)

3. Monitor health
   get_flow_health_status(pg_id)

❌ DON'T: Start processors before enabling services
   - Processors will fail validation
   - Must stop, enable services, then restart

🛡️ SAFETY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ DO: Test in development first
   - Set NIFI_READONLY=true for exploration
   - Set NIFI_READONLY=false only when building

✅ DO: Use bulk operations
   - stop_all_processors_in_group() before changes
   - start_all_processors_in_group() after changes

✅ DO: Check health regularly
   - get_flow_health_status(pg_id)
   - Monitor for errors and backpressure

"""
    
    @staticmethod
    def validate_flow_structure(flow_components: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """
        Validate flow structure against best practices.
        
        Args:
            flow_components: Dictionary containing flow components
            
        Returns:
            Tuple of (is_valid, errors, suggestions)
        """
        errors = []
        suggestions = []
        
        # Check if using process groups
        pg_id = flow_components.get("process_group_id")
        root_id = flow_components.get("root_id")
        
        if pg_id == root_id:
            errors.append("❌ Building directly on root canvas")
            suggestions.append("✅ Create a process group first for better organization")
            suggestions.append("   Example: create_process_group(root_id, 'My Pipeline')")
        
        # Check for controller services before processors
        has_services = flow_components.get("controller_services", [])
        has_processors = flow_components.get("processors", [])
        
        if has_processors and not has_services:
            suggestions.append("💡 Consider if your processors need controller services")
            suggestions.append("   (DBCPConnectionPool, RecordReaders, RecordWriters, etc.)")
        
        # Check for connections
        processors_count = len(has_processors)
        connections_count = len(flow_components.get("connections", []))
        
        if processors_count > 1 and connections_count == 0:
            errors.append("❌ Multiple processors but no connections")
            suggestions.append("✅ Connect processors with create_connection()")
        
        is_valid = len(errors) == 0
        return is_valid, errors, suggestions
    
    @staticmethod
    def get_recommended_workflow_for_request(user_request: str) -> str:
        """
        Get recommended workflow for a user's flow building request.
        
        Args:
            user_request: User's flow description
            
        Returns:
            Recommended workflow steps
        """
        should_create_pg, pg_name = NiFiBestPractices.should_create_process_group_for_flow(user_request)
        
        workflow = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║ Recommended Workflow for: {user_request[:50]}{'...' if len(user_request) > 50 else ''}
╚══════════════════════════════════════════════════════════════════════════════╝

📋 STEP-BY-STEP WORKFLOW:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣  CREATE PROCESS GROUP (Recommended)
    
    Why: Keeps your flow organized and manageable
    Command: create_process_group(root_id, "{pg_name}")
    
    This creates a dedicated container for your flow.

2️⃣  CREATE CONTROLLER SERVICES (If needed)
    
    For database flows:
    - DBCPConnectionPool (for JDBC connections)
    - CSVReader / JsonRecordSetWriter (for record processing)
    
    Command: create_controller_service(pg_id, service_type, "Service Name")

3️⃣  ENABLE CONTROLLER SERVICES
    
    Services must be enabled before processors can use them.
    Command: enable_all_controller_services_in_group(pg_id)

4️⃣  BUILD YOUR FLOW
    
    - Create processors: create_processor(pg_id, processor_type, name)
    - Configure processors: update_processor_config(processor_id, version, properties)
    - Connect processors: create_connection(pg_id, source_id, dest_id, relationships)

5️⃣  START YOUR FLOW
    
    Bulk start all processors at once (fast!):
    Command: start_all_processors_in_group(pg_id)

6️⃣  MONITOR HEALTH
    
    Check if everything is running correctly:
    Command: get_flow_health_status(pg_id)

💡 TIPS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Use descriptive names for components
• Handle all processor relationships (success, failure, etc.)
• Test with small data volumes first
• Use parameter contexts for environment-specific config
• Monitor for errors with get_flow_health_status()

"""
        return workflow


class SmartFlowBuilder:
    """Intelligent flow builder that follows best practices automatically."""
    
    def __init__(self, client):
        """
        Initialize smart flow builder.
        
        Args:
            client: NiFiClient instance
        """
        self.client = client
        self.current_process_group = None
    
    def start_new_flow(self, flow_name: str, parent_pg_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Start a new flow following best practices.
        
        Automatically creates a process group for organization.
        
        Args:
            flow_name: Name for the flow/process group
            parent_pg_id: Parent process group ID (defaults to root)
            
        Returns:
            Created process group details
        """
        if parent_pg_id is None:
            root = self.client.get_root_process_group()
            # NiFi API returns {"processGroupFlow": {"id": "root-id", ...}}
            parent_pg_id = root.get("processGroupFlow", {}).get("id") or root.get("id", "root")
        
        # Create process group for the flow
        pg = self.client.create_process_group(parent_pg_id, flow_name)
        self.current_process_group = pg["id"]
        
        return {
            "process_group": pg,
            "message": f"✅ Created process group '{flow_name}' for your flow",
            "best_practice": "Flows should always be created in process groups, not on root canvas",
            "next_steps": [
                "Create controller services (if needed)",
                "Add processors to this group",
                "Connect processors",
                "Start the flow"
            ]
        }
    
    def get_current_process_group(self) -> Optional[str]:
        """Get current process group ID."""
        return self.current_process_group

