"""
Flow Builder - Intelligent NiFi flow construction with requirements gathering

This module provides high-level flow building capabilities that understand
common data integration patterns and guide users through requirements.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class FlowRequirement:
    """Represents a requirement that must be gathered from the user"""
    name: str
    description: str
    required: bool = True
    default: Optional[str] = None
    validation: Optional[str] = None  # Validation hint
    example: Optional[str] = None
    

@dataclass
class FlowTemplate:
    """Template for building a specific type of flow"""
    name: str
    description: str
    requirements: List[FlowRequirement] = field(default_factory=list)
    processor_types: List[str] = field(default_factory=list)  # Processors needed
    

class FlowPatternLibrary:
    """Library of common NiFi flow patterns with their requirements"""
    
    @staticmethod
    def sql_server_to_iceberg() -> FlowTemplate:
        """SQL Server to Iceberg data migration flow"""
        return FlowTemplate(
            name="SQL Server to Iceberg",
            description="Extract data from SQL Server and write to Iceberg tables",
            requirements=[
                # SQL Server Source
                FlowRequirement(
                    name="sql_server_host",
                    description="SQL Server hostname or IP address",
                    example="sqlserver.example.com"
                ),
                FlowRequirement(
                    name="sql_server_port",
                    description="SQL Server port",
                    default="1433",
                    example="1433"
                ),
                FlowRequirement(
                    name="sql_server_database",
                    description="Database name to query",
                    example="ProductionDB"
                ),
                FlowRequirement(
                    name="sql_server_username",
                    description="SQL Server username",
                    example="nifi_user"
                ),
                FlowRequirement(
                    name="sql_server_password",
                    description="SQL Server password (will be stored as sensitive property)",
                    example="********"
                ),
                FlowRequirement(
                    name="sql_query",
                    description="SQL query to extract data",
                    example="SELECT * FROM customers WHERE updated_date > ?",
                    required=False
                ),
                FlowRequirement(
                    name="sql_table",
                    description="Table name (if not using custom query)",
                    example="customers",
                    required=False
                ),
                
                # Iceberg Target
                FlowRequirement(
                    name="iceberg_catalog_uri",
                    description="Iceberg catalog URI",
                    example="thrift://iceberg-catalog:9083"
                ),
                FlowRequirement(
                    name="iceberg_warehouse_path",
                    description="Iceberg warehouse path (S3 or HDFS)",
                    example="s3://my-bucket/warehouse"
                ),
                FlowRequirement(
                    name="iceberg_table_name",
                    description="Target Iceberg table name",
                    example="default.customers"
                ),
                
                # Flow Configuration
                FlowRequirement(
                    name="schedule_interval",
                    description="How often to run the flow",
                    default="1 hour",
                    example="5 min, 1 hour, 1 day"
                ),
                FlowRequirement(
                    name="batch_size",
                    description="Number of records per batch",
                    default="10000",
                    example="1000, 10000, 100000"
                ),
            ],
            processor_types=[
                "org.apache.nifi.processors.standard.GenerateTableFetch",
                "org.apache.nifi.processors.standard.ExecuteSQLRecord",
                "org.apache.nifi.dbcp.DBCPConnectionPool",
                "org.apache.nifi.serialization.JsonRecordSetWriter",
                "org.apache.nifi.serialization.AvroReader",
                # Iceberg processors would be custom/extension
                "org.apache.nifi.processors.iceberg.PutIceberg"
            ]
        )
    
    @staticmethod
    def kafka_to_s3() -> FlowTemplate:
        """Kafka to S3 data pipeline"""
        return FlowTemplate(
            name="Kafka to S3",
            description="Consume from Kafka and write to S3 with optional transformations",
            requirements=[
                FlowRequirement(
                    name="kafka_brokers",
                    description="Kafka broker addresses (comma-separated)",
                    example="broker1:9092,broker2:9092"
                ),
                FlowRequirement(
                    name="kafka_topic",
                    description="Kafka topic to consume from",
                    example="events"
                ),
                FlowRequirement(
                    name="kafka_consumer_group",
                    description="Consumer group ID",
                    example="nifi-s3-consumer"
                ),
                FlowRequirement(
                    name="s3_bucket",
                    description="S3 bucket name",
                    example="my-data-lake"
                ),
                FlowRequirement(
                    name="s3_prefix",
                    description="S3 key prefix/path",
                    example="raw/events/"
                ),
                FlowRequirement(
                    name="file_format",
                    description="Output file format",
                    default="parquet",
                    example="parquet, json, avro"
                ),
            ],
            processor_types=[
                "org.apache.nifi.processors.kafka.pubsub.ConsumeKafka_2_6",
                "org.apache.nifi.processors.aws.s3.PutS3Object",
            ]
        )
    
    @staticmethod
    def rest_api_to_database() -> FlowTemplate:
        """REST API to Database integration"""
        return FlowTemplate(
            name="REST API to Database",
            description="Fetch data from REST API and load into database",
            requirements=[
                FlowRequirement(
                    name="api_url",
                    description="REST API endpoint URL",
                    example="https://api.example.com/v1/data"
                ),
                FlowRequirement(
                    name="api_auth_type",
                    description="Authentication type",
                    default="none",
                    example="none, bearer, basic"
                ),
                FlowRequirement(
                    name="api_token",
                    description="API token/key (if auth required)",
                    required=False,
                    example="Bearer xyz123..."
                ),
                FlowRequirement(
                    name="db_host",
                    description="Database hostname",
                    example="postgres.example.com"
                ),
                FlowRequirement(
                    name="db_port",
                    description="Database port",
                    example="5432"
                ),
                FlowRequirement(
                    name="db_name",
                    description="Database name",
                    example="analytics"
                ),
                FlowRequirement(
                    name="db_table",
                    description="Target table name",
                    example="api_data"
                ),
            ],
            processor_types=[
                "org.apache.nifi.processors.standard.InvokeHTTP",
                "org.apache.nifi.processors.standard.ConvertRecord",
                "org.apache.nifi.processors.standard.PutDatabaseRecord",
            ]
        )
    
    @staticmethod
    def file_watcher_to_processing() -> FlowTemplate:
        """Watch directory and process files"""
        return FlowTemplate(
            name="File Watcher to Processing",
            description="Monitor directory for files and process them",
            requirements=[
                FlowRequirement(
                    name="source_directory",
                    description="Directory to monitor for files",
                    example="/data/incoming"
                ),
                FlowRequirement(
                    name="file_pattern",
                    description="File pattern to match",
                    default=".*\\.csv",
                    example=".*\\.csv, .*\\.json, data-.*\\.txt"
                ),
                FlowRequirement(
                    name="target_directory",
                    description="Directory to write processed files",
                    example="/data/processed"
                ),
                FlowRequirement(
                    name="archive_directory",
                    description="Directory to archive original files",
                    example="/data/archive",
                    required=False
                ),
            ],
            processor_types=[
                "org.apache.nifi.processors.standard.GetFile",
                "org.apache.nifi.processors.standard.UpdateAttribute",
                "org.apache.nifi.processors.standard.PutFile",
            ]
        )
    
    @staticmethod
    def database_to_files() -> FlowTemplate:
        """Generic database export to files - works with any JDBC-compatible database"""
        return FlowTemplate(
            name="Database to Files",
            description="""
            Extract data from any database and write to files (JSON, Avro, CSV, etc.).
            
            Supports: MySQL, PostgreSQL, Oracle, SQL Server, MariaDB, etc.
            
            💡 RECOMMENDED APPROACH:
            1. For CDC/real-time: Check if NiFi has a CDC processor for your database
               - MySQL: CaptureChangeMySQL (no JDBC driver needed!)
               - MongoDB: CaptureChangeMongoDB
               - SQL Server: CDC via Debezium connectors
            2. For full exports: Use this JDBC-based approach
            
            ⚠️ JDBC Driver Required: Your NiFi administrator must install the appropriate 
            JDBC driver on the NiFi server(s). Contact them if you encounter ClassNotFoundException errors.
            """,
            requirements=[
                FlowRequirement(
                    name="database_type",
                    description="Type of database (mysql, postgresql, oracle, sqlserver, etc.)",
                    example="mysql"
                ),
                FlowRequirement(
                    name="host",
                    description="Database hostname or IP address",
                    example="db.example.com"
                ),
                FlowRequirement(
                    name="port",
                    description="Database port",
                    example="3306 (MySQL), 5432 (PostgreSQL), 1433 (SQL Server)"
                ),
                FlowRequirement(
                    name="database_name",
                    description="Database name to query",
                    example="mydb"
                ),
                FlowRequirement(
                    name="username",
                    description="Database username",
                    example="nifi_user"
                ),
                FlowRequirement(
                    name="password",
                    description="Database password",
                    example="********"
                ),
                FlowRequirement(
                    name="tables_or_query",
                    description="Comma-separated table names OR custom SQL query",
                    example="customers,orders OR SELECT * FROM customers WHERE updated > NOW() - INTERVAL 1 DAY",
                    required=False
                ),
                FlowRequirement(
                    name="output_format",
                    description="Output format (json, avro, csv, parquet)",
                    example="json",
                    default="json"
                ),
                FlowRequirement(
                    name="output_directory",
                    description="Directory to write files",
                    example="/tmp",
                    default="/tmp"
                ),
            ],
            processor_types=[
                "org.apache.nifi.dbcp.DBCPConnectionPool",
                "org.apache.nifi.processors.standard.QueryDatabaseTable",  # Or ExecuteSQL
                "org.apache.nifi.processors.standard.ConvertRecord",
                "org.apache.nifi.processors.standard.UpdateAttribute",
                "org.apache.nifi.processors.standard.PutFile"
            ]
        )
    
    @staticmethod
    def files_to_database() -> FlowTemplate:
        """Generic file ingestion to database - works with any JDBC-compatible database"""
        return FlowTemplate(
            name="Files to Database",
            description="""
            Ingest files (CSV, JSON, Avro, Parquet, XML) and write to any database.
            
            Supports: MySQL, PostgreSQL, Oracle, SQL Server, MariaDB, etc.
            Common use cases: Data lake → database, file uploads to DB, ETL pipelines
            
            ⚠️ JDBC Driver Required: Your NiFi administrator must install the JDBC driver for your target database.
            """,
            requirements=[
                FlowRequirement(
                    name="source_directory",
                    description="Directory containing files to ingest",
                    example="/data/input"
                ),
                FlowRequirement(
                    name="file_pattern",
                    description="Pattern to match files (regex or glob)",
                    example="*.csv or *.json",
                    default="*"
                ),
                FlowRequirement(
                    name="input_format",
                    description="Input file format (csv, json, avro, parquet, xml)",
                    example="csv"
                ),
                FlowRequirement(
                    name="database_type",
                    description="Type of target database",
                    example="postgresql"
                ),
                FlowRequirement(
                    name="host",
                    description="Database hostname",
                    example="db.example.com"
                ),
                FlowRequirement(
                    name="port",
                    description="Database port",
                    example="5432"
                ),
                FlowRequirement(
                    name="database_name",
                    description="Target database name",
                    example="warehouse"
                ),
                FlowRequirement(
                    name="table_name",
                    description="Target table name",
                    example="staging_data"
                ),
                FlowRequirement(
                    name="username",
                    description="Database username",
                    example="etl_user"
                ),
                FlowRequirement(
                    name="password",
                    description="Database password",
                    example="********"
                ),
                FlowRequirement(
                    name="insert_mode",
                    description="INSERT or UPSERT (update if exists)",
                    example="INSERT",
                    default="INSERT"
                ),
            ],
            processor_types=[
                "org.apache.nifi.processors.standard.ListFile",
                "org.apache.nifi.processors.standard.FetchFile",
                "org.apache.nifi.processors.standard.ConvertRecord",
                "org.apache.nifi.processors.standard.PutDatabaseRecord",
                "org.apache.nifi.dbcp.DBCPConnectionPool"
            ]
        )
    
    @staticmethod
    def object_storage_to_database() -> FlowTemplate:
        """Cloud object storage (S3/Azure/GCS) to database"""
        return FlowTemplate(
            name="Object Storage to Database",
            description="""
            Ingest files from cloud storage (S3, Azure Blob, GCS) and load to database.
            
            Common use cases: Data lake → warehouse, cloud ETL, analytics pipelines
            """,
            requirements=[
                FlowRequirement(
                    name="cloud_provider",
                    description="Cloud provider (aws, azure, gcp)",
                    example="aws"
                ),
                FlowRequirement(
                    name="bucket_or_container",
                    description="S3 bucket / Azure container / GCS bucket name",
                    example="my-data-lake"
                ),
                FlowRequirement(
                    name="path_prefix",
                    description="Path prefix or folder to scan",
                    example="data/raw/",
                    required=False
                ),
                FlowRequirement(
                    name="file_pattern",
                    description="Pattern to match files",
                    example="*.parquet",
                    default="*"
                ),
                FlowRequirement(
                    name="credentials_type",
                    description="How to authenticate (access_key, iam_role, managed_identity, service_account)",
                    example="access_key"
                ),
                FlowRequirement(
                    name="database_type",
                    description="Target database type",
                    example="postgresql"
                ),
                FlowRequirement(
                    name="database_connection_string",
                    description="JDBC connection string",
                    example="jdbc:postgresql://host:5432/dbname"
                ),
                FlowRequirement(
                    name="table_name",
                    description="Target table name",
                    example="analytics_data"
                ),
            ],
            processor_types=[
                "org.apache.nifi.processors.aws.s3.ListS3",  # Or Azure/GCS equivalent
                "org.apache.nifi.processors.aws.s3.FetchS3Object",
                "org.apache.nifi.processors.standard.ConvertRecord",
                "org.apache.nifi.processors.standard.PutDatabaseRecord"
            ]
        )
    
    @staticmethod
    def database_to_database() -> FlowTemplate:
        """Database to database replication/sync"""
        return FlowTemplate(
            name="Database to Database",
            description="""
            Replicate or synchronize data between databases.
            
            Common use cases: Database migration, cross-database ETL, data warehouse loading
            Supports: Any JDBC-compatible databases (MySQL ↔ PostgreSQL, Oracle → SQL Server, etc.)
            """,
            requirements=[
                FlowRequirement(
                    name="source_database_type",
                    description="Source database type",
                    example="mysql"
                ),
                FlowRequirement(
                    name="source_host",
                    description="Source database host",
                    example="source-db.example.com"
                ),
                FlowRequirement(
                    name="source_port",
                    description="Source database port",
                    example="3306"
                ),
                FlowRequirement(
                    name="source_database",
                    description="Source database name",
                    example="production"
                ),
                FlowRequirement(
                    name="source_username",
                    description="Source database username",
                    example="readonly_user"
                ),
                FlowRequirement(
                    name="source_password",
                    description="Source database password",
                    example="********"
                ),
                FlowRequirement(
                    name="target_database_type",
                    description="Target database type",
                    example="postgresql"
                ),
                FlowRequirement(
                    name="target_host",
                    description="Target database host",
                    example="target-db.example.com"
                ),
                FlowRequirement(
                    name="target_port",
                    description="Target database port",
                    example="5432"
                ),
                FlowRequirement(
                    name="target_database",
                    description="Target database name",
                    example="warehouse"
                ),
                FlowRequirement(
                    name="target_username",
                    description="Target database username",
                    example="write_user"
                ),
                FlowRequirement(
                    name="target_password",
                    description="Target database password",
                    example="********"
                ),
                FlowRequirement(
                    name="sync_mode",
                    description="full (one-time copy) or incremental (ongoing sync)",
                    example="incremental",
                    default="incremental"
                ),
                FlowRequirement(
                    name="tables",
                    description="Comma-separated list of tables to sync",
                    example="users,orders,products"
                ),
            ],
            processor_types=[
                "org.apache.nifi.dbcp.DBCPConnectionPool",  # Source
                "org.apache.nifi.dbcp.DBCPConnectionPool",  # Target  
                "org.apache.nifi.processors.standard.QueryDatabaseTable",
                "org.apache.nifi.processors.standard.ConvertRecord",
                "org.apache.nifi.processors.standard.PutDatabaseRecord"
            ]
        )
    
    @staticmethod
    def streaming_to_database() -> FlowTemplate:
        """Streaming platforms (Kafka/Pulsar) to database"""
        return FlowTemplate(
            name="Streaming to Database",
            description="""
            Consume streaming data from Kafka/Pulsar and load to database in real-time.
            
            Common use cases: Event processing, real-time analytics, stream-to-warehouse
            """,
            requirements=[
                FlowRequirement(
                    name="streaming_platform",
                    description="Streaming platform (kafka, pulsar)",
                    example="kafka"
                ),
                FlowRequirement(
                    name="brokers",
                    description="Comma-separated list of broker addresses",
                    example="broker1:9092,broker2:9092"
                ),
                FlowRequirement(
                    name="topic",
                    description="Topic name to consume",
                    example="events"
                ),
                FlowRequirement(
                    name="consumer_group",
                    description="Consumer group ID",
                    example="nifi-consumer-group",
                    default="nifi-consumer"
                ),
                FlowRequirement(
                    name="message_format",
                    description="Message format (json, avro, protobuf, csv)",
                    example="json",
                    default="json"
                ),
                FlowRequirement(
                    name="database_type",
                    description="Target database type",
                    example="postgresql"
                ),
                FlowRequirement(
                    name="database_connection_string",
                    description="JDBC connection string",
                    example="jdbc:postgresql://host:5432/events_db"
                ),
                FlowRequirement(
                    name="table_name",
                    description="Target table name",
                    example="events"
                ),
                FlowRequirement(
                    name="batch_size",
                    description="Number of records to batch before insert",
                    example="1000",
                    default="1000"
                ),
            ],
            processor_types=[
                "org.apache.nifi.processors.kafka.pubsub.ConsumeKafka",
                "org.apache.nifi.processors.standard.ConvertRecord",
                "org.apache.nifi.processors.standard.PutDatabaseRecord",
                "org.apache.nifi.dbcp.DBCPConnectionPool"
            ]
        )
    
    @staticmethod
    def ftp_to_processing() -> FlowTemplate:
        """FTP/SFTP file ingestion and processing"""
        return FlowTemplate(
            name="FTP/SFTP to Processing",
            description="""
            Monitor FTP/SFTP servers for new files and process them.
            
            Common use cases: Partner data exchange, legacy system integration, B2B file transfers
            """,
            requirements=[
                FlowRequirement(
                    name="protocol",
                    description="Protocol (ftp or sftp)",
                    example="sftp"
                ),
                FlowRequirement(
                    name="host",
                    description="FTP/SFTP server hostname",
                    example="ftp.partner.com"
                ),
                FlowRequirement(
                    name="port",
                    description="Port number",
                    example="22 (SFTP), 21 (FTP)",
                    default="22"
                ),
                FlowRequirement(
                    name="username",
                    description="FTP/SFTP username",
                    example="transfer_user"
                ),
                FlowRequirement(
                    name="password",
                    description="Password or leave blank for key-based auth",
                    example="********",
                    required=False
                ),
                FlowRequirement(
                    name="remote_path",
                    description="Remote directory path to monitor",
                    example="/incoming/data"
                ),
                FlowRequirement(
                    name="file_pattern",
                    description="Pattern to match files",
                    example="*.csv",
                    default="*"
                ),
                FlowRequirement(
                    name="polling_interval",
                    description="How often to check for new files",
                    example="5 min",
                    default="5 min"
                ),
                FlowRequirement(
                    name="destination_type",
                    description="Where to send processed files (local, s3, database)",
                    example="local"
                ),
            ],
            processor_types=[
                "org.apache.nifi.processors.standard.ListSFTP",  # Or ListFTP
                "org.apache.nifi.processors.standard.FetchSFTP",
                "org.apache.nifi.processors.standard.UnpackContent",
                "org.apache.nifi.processors.standard.ConvertRecord",
                "org.apache.nifi.processors.standard.PutFile"  # Or PutS3, PutDatabase, etc.
            ]
        )
    
    @staticmethod
    def data_transformation() -> FlowTemplate:
        """Generic data transformation pipeline"""
        return FlowTemplate(
            name="Data Transformation",
            description="""
            Transform data from one format to another with validation and enrichment.
            
            Common use cases: ETL, data cleansing, format conversion, schema evolution
            Supports: JSON ↔ CSV ↔ Avro ↔ Parquet ↔ XML
            """,
            requirements=[
                FlowRequirement(
                    name="source_type",
                    description="Where data comes from (file, database, api, kafka)",
                    example="file"
                ),
                FlowRequirement(
                    name="source_format",
                    description="Input data format (csv, json, avro, xml, parquet)",
                    example="csv"
                ),
                FlowRequirement(
                    name="target_format",
                    description="Output data format (csv, json, avro, xml, parquet)",
                    example="parquet"
                ),
                FlowRequirement(
                    name="transformations",
                    description="Transformations needed (filter, enrich, aggregate, pivot, etc.)",
                    example="filter invalid records, add timestamp",
                    required=False
                ),
                FlowRequirement(
                    name="destination_type",
                    description="Where to send results (file, database, s3, kafka)",
                    example="s3"
                ),
                FlowRequirement(
                    name="error_handling",
                    description="How to handle bad records (skip, route_to_dead_letter, fail)",
                    example="route_to_dead_letter",
                    default="route_to_dead_letter"
                ),
            ],
            processor_types=[
                "org.apache.nifi.processors.standard.ConvertRecord",
                "org.apache.nifi.processors.standard.QueryRecord",
                "org.apache.nifi.processors.standard.UpdateRecord",
                "org.apache.nifi.processors.standard.ValidateRecord",
                "org.apache.nifi.processors.standard.RouteOnAttribute"
            ]
        )
    
    @staticmethod
    def log_aggregation() -> FlowTemplate:
        """Log file collection and aggregation"""
        return FlowTemplate(
            name="Log Aggregation",
            description="""
            Collect logs from multiple sources and aggregate to central location.
            
            Common use cases: Application logging, security logs, audit trails, observability
            """,
            requirements=[
                FlowRequirement(
                    name="log_source_type",
                    description="Log source (file, syslog, http, kafka)",
                    example="file"
                ),
                FlowRequirement(
                    name="log_locations",
                    description="Comma-separated log file paths or endpoints",
                    example="/var/log/app/*.log, /var/log/nginx/*.log"
                ),
                FlowRequirement(
                    name="log_format",
                    description="Log format (json, syslog, apache, custom)",
                    example="json",
                    default="json"
                ),
                FlowRequirement(
                    name="parse_logs",
                    description="Parse logs or keep as raw text (yes/no)",
                    example="yes",
                    default="yes"
                ),
                FlowRequirement(
                    name="destination_type",
                    description="Where to send logs (elasticsearch, s3, kafka, splunk)",
                    example="elasticsearch"
                ),
                FlowRequirement(
                    name="retention_days",
                    description="How long to retain logs",
                    example="30",
                    default="30"
                ),
                FlowRequirement(
                    name="add_metadata",
                    description="Add hostname, app name, environment tags (yes/no)",
                    example="yes",
                    default="yes"
                ),
            ],
            processor_types=[
                "org.apache.nifi.processors.standard.TailFile",  # Or ListenSyslog, etc.
                "org.apache.nifi.processors.standard.ExtractText",
                "org.apache.nifi.processors.standard.UpdateAttribute",
                "org.apache.nifi.processors.standard.MergeContent",
                "org.apache.nifi.processors.elasticsearch.PutElasticsearch"  # Or PutS3, PublishKafka
            ]
        )
    
    @classmethod
    def get_template(cls, pattern_name: str) -> Optional[FlowTemplate]:
        """Get a flow template by name or description match"""
        patterns = {
            # Database patterns
            "database_to_files": cls.database_to_files,
            "db_to_files": cls.database_to_files,
            "database_export": cls.database_to_files,
            "files_to_database": cls.files_to_database,
            "file_to_db": cls.files_to_database,
            "database_to_database": cls.database_to_database,
            "db_to_db": cls.database_to_database,
            "database_replication": cls.database_to_database,
            "database_sync": cls.database_to_database,
            
            # Cloud/Object Storage patterns
            "object_storage_to_database": cls.object_storage_to_database,
            "s3_to_database": cls.object_storage_to_database,
            "azure_to_database": cls.object_storage_to_database,
            "gcs_to_database": cls.object_storage_to_database,
            
            # Streaming patterns
            "streaming_to_database": cls.streaming_to_database,
            "kafka_to_database": cls.streaming_to_database,
            "kafka_to_db": cls.streaming_to_database,
            "kafka_to_s3": cls.kafka_to_s3,
            "kafka_s3": cls.kafka_to_s3,
            
            # FTP patterns
            "ftp_to_processing": cls.ftp_to_processing,
            "sftp_to_processing": cls.ftp_to_processing,
            "ftp": cls.ftp_to_processing,
            
            # Transform patterns
            "data_transformation": cls.data_transformation,
            "transform": cls.data_transformation,
            "etl": cls.data_transformation,
            
            # Log patterns
            "log_aggregation": cls.log_aggregation,
            "logs": cls.log_aggregation,
            "log_collection": cls.log_aggregation,
            
            # Specific patterns (for backwards compatibility)
            "sql_server_to_iceberg": cls.sql_server_to_iceberg,
            "sql_to_iceberg": cls.sql_server_to_iceberg,
            "database_to_iceberg": cls.sql_server_to_iceberg,
            "rest_api_to_database": cls.rest_api_to_database,
            "api_to_db": cls.rest_api_to_database,
            "file_watcher": cls.file_watcher_to_processing,
            "file_monitoring": cls.file_watcher_to_processing,
        }
        
        pattern_key = pattern_name.lower().replace(" ", "_").replace("-", "_")
        if pattern_key in patterns:
            return patterns[pattern_key]()
        
        # Try fuzzy matching
        for key, func in patterns.items():
            if key in pattern_key or pattern_key in key:
                return func()
        
        return None
    
    @classmethod
    def list_available_templates(cls) -> List[Dict[str, str]]:
        """List all available flow templates"""
        return [
            # Database patterns
            {"name": "Database → Files", "key": "database_to_files"},
            {"name": "Files → Database", "key": "files_to_database"},
            {"name": "Database → Database", "key": "database_to_database"},
            {"name": "Database → Iceberg", "key": "sql_server_to_iceberg"},
            
            # Cloud/Object Storage patterns
            {"name": "Object Storage → Database (S3/Azure/GCS)", "key": "object_storage_to_database"},
            {"name": "Kafka → S3", "key": "kafka_to_s3"},
            
            # Streaming patterns
            {"name": "Streaming → Database (Kafka/Pulsar)", "key": "streaming_to_database"},
            
            # File patterns
            {"name": "FTP/SFTP → Processing", "key": "ftp_to_processing"},
            {"name": "File Watcher → Processing", "key": "file_watcher"},
            
            # REST API patterns
            {"name": "REST API → Database", "key": "rest_api_to_database"},
            
            # ETL patterns
            {"name": "Data Transformation (ETL)", "key": "data_transformation"},
            {"name": "Log Aggregation", "key": "log_aggregation"},
        ]


class FlowBuilderGuide:
    """Guides users through building flows by gathering requirements"""
    
    @staticmethod
    def identify_pattern(user_request: str) -> Optional[FlowTemplate]:
        """
        Analyze user request and identify matching flow pattern using generic keyword detection.
        
        Examples:
            "Copy MySQL tables to JSON files" → Database → Files
            "Load CSV files into PostgreSQL" → Files → Database
            "Sync Oracle to Snowflake" → Database → Database
            "Stream Kafka to S3" → Streaming → Object Storage
            "Transform CSV to Parquet" → Data Transformation
            "Collect logs from servers" → Log Aggregation
        """
        request_lower = user_request.lower()
        
        # Source keywords
        database_src = ["mysql", "postgres", "postgresql", "oracle", "sqlserver", "mariadb", "mssql", "database", "db", "sql"]
        file_src = ["file", "files", "csv", "json", "xml", "avro", "parquet"]
        cloud_src = ["s3", "azure blob", "gcs", "google cloud storage", "object storage", "bucket"]
        streaming_src = ["kafka", "pulsar", "kinesis", "stream", "event"]
        ftp_src = ["ftp", "sftp", "ssh"]
        api_src = ["api", "rest", "http", "endpoint"]
        log_src = ["log", "logs", "logging", "syslog"]
        
        # Destination/action keywords
        database_dest = has_database = any(word in request_lower for word in database_src)
        file_dest = any(word in request_lower for word in file_src)
        cloud_dest = any(word in request_lower for word in cloud_src)
        
        # Action keywords
        transform_keywords = ["transform", "convert", "etl", "clean", "enrich", "validate"]
        sync_keywords = ["sync", "replicate", "migrate", "copy", "move"]
        watch_keywords = ["watch", "monitor", "poll"]
        aggregate_keywords = ["aggregate", "collect", "gather", "centralize"]
        
        # Pattern matching logic (order matters - most specific first)
        
        # Iceberg pattern (very specific)
        if "iceberg" in request_lower and any(word in request_lower for word in database_src):
            return FlowPatternLibrary.get_template("sql_server_to_iceberg")
        
        # Streaming to database
        if any(word in request_lower for word in streaming_src) and database_dest:
            return FlowPatternLibrary.get_template("streaming_to_database")
        
        # Kafka to S3
        if "kafka" in request_lower and "s3" in request_lower:
            return FlowPatternLibrary.get_template("kafka_to_s3")
        
        # Object storage to database
        if any(word in request_lower for word in cloud_src) and database_dest:
            return FlowPatternLibrary.get_template("object_storage_to_database")
        
        # FTP/SFTP ingestion
        if any(word in request_lower for word in ftp_src):
            return FlowPatternLibrary.get_template("ftp_to_processing")
        
        # Log aggregation
        if any(word in request_lower for word in log_src) and any(word in request_lower for word in aggregate_keywords):
            return FlowPatternLibrary.get_template("log_aggregation")
        
        # Database to database (sync/replication)
        if database_dest and any(word in request_lower for word in sync_keywords):
            # Check if there are indicators of source database too
            db_count = sum(1 for word in database_src if word in request_lower)
            if db_count >= 2 or "to" in request_lower:  # e.g., "mysql to postgres"
                return FlowPatternLibrary.get_template("database_to_database")
        
        # Files to database
        if any(word in request_lower for word in file_src) and database_dest and \
           any(word in request_lower for word in ["load", "import", "ingest", "insert", "to"]):
            return FlowPatternLibrary.get_template("files_to_database")
        
        # Database to files
        if database_dest and file_dest and \
           any(word in request_lower for word in ["export", "extract", "dump", "copy", "save"]):
            return FlowPatternLibrary.get_template("database_to_files")
        
        # Data transformation
        if any(word in request_lower for word in transform_keywords):
            return FlowPatternLibrary.get_template("data_transformation")
        
        # REST API to Database
        if any(word in request_lower for word in api_src) and database_dest:
            return FlowPatternLibrary.get_template("rest_api_to_database")
        
        # File watcher
        if any(word in request_lower for word in watch_keywords) and \
           any(word in request_lower for word in ["file", "directory", "folder"]):
            return FlowPatternLibrary.get_template("file_watcher")
        
        return None
    
    @staticmethod
    def format_requirements_for_user(template: FlowTemplate) -> str:
        """
        Format requirements as a user-friendly prompt
        
        Returns a message that Claude can use to ask the user for information.
        """
        msg = f"To build a **{template.name}** flow, I need the following information:\n\n"
        msg += f"{template.description}\n\n"
        
        required_reqs = [r for r in template.requirements if r.required]
        optional_reqs = [r for r in template.requirements if not r.required]
        
        if required_reqs:
            msg += "**Required Information:**\n"
            for req in required_reqs:
                msg += f"- **{req.name.replace('_', ' ').title()}**: {req.description}\n"
                if req.example:
                    msg += f"  Example: `{req.example}`\n"
                if req.default:
                    msg += f"  Default: `{req.default}`\n"
            msg += "\n"
        
        if optional_reqs:
            msg += "**Optional Information:**\n"
            for req in optional_reqs:
                msg += f"- **{req.name.replace('_', ' ').title()}**: {req.description}\n"
                if req.example:
                    msg += f"  Example: `{req.example}`\n"
                if req.default:
                    msg += f"  Default: `{req.default}`\n"
            msg += "\n"
        
        msg += "Please provide these details and I'll build the flow for you!"
        return msg
    
    @staticmethod
    def validate_requirements(template: FlowTemplate, user_values: Dict[str, str]) -> Tuple[bool, List[str]]:
        """
        Validate that all required values are provided
        
        Returns (is_valid, list_of_missing_fields)
        """
        missing = []
        
        for req in template.requirements:
            if req.required:
                value = user_values.get(req.name)
                if not value or value.strip() == "":
                    missing.append(req.name)
        
        return (len(missing) == 0, missing)


class FlowPositioner:
    """Helps position processors on the canvas in a visually pleasing way"""
    
    @staticmethod
    def linear_flow(processor_count: int, start_x: float = 100, start_y: float = 200, 
                    spacing_x: float = 350) -> List[Tuple[float, float]]:
        """Position processors in a horizontal line"""
        positions = []
        for i in range(processor_count):
            positions.append((start_x + (i * spacing_x), start_y))
        return positions
    
    @staticmethod
    def branching_flow(main_count: int, branch_count: int, 
                      start_x: float = 100, start_y: float = 200) -> List[Tuple[float, float]]:
        """Position processors for a flow with branching logic"""
        positions = []
        
        # Main flow (horizontal)
        for i in range(main_count):
            positions.append((start_x + (i * 350), start_y))
        
        # Branches (vertical from last main processor)
        branch_x = start_x + ((main_count - 1) * 350) + 350
        branch_spacing = 150
        branch_start_y = start_y - (branch_count * branch_spacing / 2)
        
        for i in range(branch_count):
            positions.append((branch_x, branch_start_y + (i * branch_spacing)))
        
        return positions


# Convenience function for MCP integration
def analyze_flow_request(user_request: str) -> Dict[str, Any]:
    """
    Analyze a user's flow building request and return guidance
    
    Returns:
        {
            'pattern_found': bool,
            'template': FlowTemplate or None,
            'requirements_prompt': str,
            'suggested_processors': List[str]
        }
    """
    template = FlowBuilderGuide.identify_pattern(user_request)
    
    if template:
        return {
            'pattern_found': True,
            'template_name': template.name,
            'template_description': template.description,
            'requirements_prompt': FlowBuilderGuide.format_requirements_for_user(template),
            'required_processors': template.processor_types,
            'requirement_count': len([r for r in template.requirements if r.required])
        }
    else:
        return {
            'pattern_found': False,
            'template_name': None,
            'available_templates': FlowPatternLibrary.list_available_templates(),
            'message': "I couldn't identify a specific pattern. Available templates: " + 
                      ", ".join([t['name'] for t in FlowPatternLibrary.list_available_templates()])
        }

