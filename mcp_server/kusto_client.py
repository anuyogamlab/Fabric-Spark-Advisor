"""
Kusto (Azure Data Explorer) Client
Handles queries to Kusto database (Eventhouse) for Spark telemetry data
"""
import os
from typing import Optional, List, Dict, Any
from azure.kusto.data import KustoClient as AzureKustoClient, KustoConnectionStringBuilder
from azure.identity import DefaultAzureCredential, ClientSecretCredential, AzureCliCredential
from dotenv import load_dotenv

load_dotenv()


class KustoClient:
    def __init__(self):
        self.cluster_uri = os.getenv("KUSTO_CLUSTER_URI")
        self.database = os.getenv("KUSTO_DATABASE")
        
        # Check for preferred authentication method (avoids noisy warnings)
        auth_preference = os.getenv("AZURE_AUTH_METHOD", "auto").lower()
        
        credential = None
        auth_method = "Failed"
        
        # If explicitly set to use Azure CLI (common in dev), try it first
        if auth_preference == "cli":
            try:
                credential = AzureCliCredential()
                kcsb = KustoConnectionStringBuilder.with_azure_token_credential(
                    self.cluster_uri,
                    credential
                )
                self.client = AzureKustoClient(kcsb)
                self.client.execute(self.database, ".show databases | limit 1")
                auth_method = "Azure CLI"
                print(f"✅ Connected to Kusto using {auth_method}")
                return
            except Exception as e:
                print(f"⚠️ Azure CLI auth failed: {e}")
                # Fall through to other methods
        
        # Try Client Secret if credentials are provided
        tenant_id = os.getenv("AZURE_TENANT_ID")
        client_id = os.getenv("AZURE_CLIENT_ID")
        client_secret = os.getenv("AZURE_CLIENT_SECRET")
        
        if all([tenant_id, client_id, client_secret]) and tenant_id != "your-tenant-id-here":
            try:
                credential = ClientSecretCredential(tenant_id, client_id, client_secret)
                kcsb = KustoConnectionStringBuilder.with_azure_token_credential(
                    self.cluster_uri,
                    credential
                )
                self.client = AzureKustoClient(kcsb)
                self.client.execute(self.database, ".show databases | limit 1")
                auth_method = "Client Secret"
                print(f"✅ Connected to Kusto using {auth_method}")
                return
            except Exception as e:
                print(f"⚠️ Client Secret auth failed: {e}")
                # Fall through
        
        # Try Azure CLI (quiet fallback for dev environments)
        try:
            credential = AzureCliCredential()
            kcsb = KustoConnectionStringBuilder.with_azure_token_credential(
                self.cluster_uri,
                credential
            )
            self.client = AzureKustoClient(kcsb)
            self.client.execute(self.database, ".show databases | limit 1")
            auth_method = "Azure CLI"
            print(f"✅ Connected to Kusto using {auth_method}")
            return
        except Exception as cli_error:
            # Last resort: try DefaultAzureCredential (for managed identity in production)
            try:
                credential = DefaultAzureCredential()
                kcsb = KustoConnectionStringBuilder.with_azure_token_credential(
                    self.cluster_uri,
                    credential
                )
                self.client = AzureKustoClient(kcsb)
                self.client.execute(self.database, ".show databases | limit 1")
                auth_method = "Default Azure Credential"
                print(f"✅ Connected to Kusto using {auth_method}")
                return
            except Exception as default_error:
                raise ValueError(
                    f"All authentication methods failed:\n"
                    f"  1. Azure CLI: {str(cli_error)}\n"
                    f"  2. Default Credential: {str(default_error)}\n"
                    f"\nTroubleshooting:\n"
                    f"  - Run 'az login' to authenticate with Azure CLI\n"
                    f"  - Or set credentials in .env:\n"
                    f"    AZURE_TENANT_ID=your-tenant-id\n"
                    f"    AZURE_CLIENT_ID=your-client-id\n"
                    f"    AZURE_CLIENT_SECRET=your-client-secret\n"
                    f"  - Or add AZURE_AUTH_METHOD=cli to .env for cleaner logs"
                )
    
    def query(self, query: str) -> Any:
        """Execute a KQL query and return results"""
        response = self.client.execute(self.database, query)
        # primary_results is a list of result tables; return the first one
        primary_results = response.primary_results
        if primary_results and len(primary_results) > 0:
            return primary_results[0]
        return None
    
    def query_to_dict_list(self, query: str) -> List[Dict[str, Any]]:
        """Execute KQL query and return results as list of dictionaries"""
        result = self.query(query)
        if not result:
            return []
        
        rows = []
        for row in result:
            row_dict = {}
            for i, col in enumerate(result.columns):
                row_dict[col.column_name] = row[i]
            rows.append(row_dict)
        return rows
    
    # ==================== MCP Tool Methods ====================
    
    def get_sparklens_recommendations(self, application_id: str) -> List[Dict[str, Any]]:
        """
        Get Spark optimization recommendations for a specific application.
        
        Args:
            application_id: The Spark application ID
            
        Returns:
            List of recommendation records with issue, severity, recommendation, category
        """
        query = f"""
        sparklens_recommedations
        | where app_id == '{application_id}'
        | project app_id, recommendation, ingestion_time()
        """
        return self.query_to_dict_list(query)
    
    def get_bad_practice_applications(self, min_violations: int = 3) -> List[Dict[str, Any]]:
        """
        Get applications with bad practices ranked by violation count.
        
        Args:
            min_violations: Minimum number of violations to include
            
        Returns:
            Ranked list of applications with violation counts
        """
        # This query looks for common bad practices across all apps
        query = f"""
        let BadPractices = sparklens_metrics
        | where metric in (
            "Executor Efficiency",
            "GC Overhead", 
            "Parallelism Score",
            "Task Skew Ratio"
        )
        | extend violation = case(
            metric == "Executor Efficiency" and value < 0.4, 1,
            metric == "GC Overhead" and value > 0.25, 1,
            metric == "Parallelism Score" and value < 0.4, 1,
            metric == "Task Skew Ratio" and value > 3.0, 1,
            0
        )
        | where violation == 1
        | summarize 
            violation_count = count(),
            issues = make_set(metric)
        by app_id;
        BadPractices
        | where violation_count >= {min_violations}
        | join kind=leftouter (
            sparklens_metadata
            | project app_id = applicationId, applicationName, artifactId
        ) on app_id
        | project 
            app_id,
            application_name = coalesce(applicationName, "Unknown"),
            artifact_id = coalesce(artifactId, "Unknown"),
            violation_count,
            issues = tostring(issues)
        | order by violation_count desc
        """
        return self.query_to_dict_list(query)
    
    def get_recent_applications(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get applications that ran recently within the specified time window.
        
        Args:
            hours: Number of hours to look back (default 24 for today)
            
        Returns:
            List of applications with basic info and health status
        """
        query = f"""
        let TimeWindow = ago({hours}h);
        let RecentApps = sparklens_metadata
        | where ingestion_time() >= TimeWindow
        | distinct applicationId, applicationName, artifactId, capacityId
        | project app_id = applicationId, app_name = applicationName, artifact_id = artifactId, capacity_id = capacityId;
        RecentApps
        | join kind=leftouter (
            sparklens_metrics
            | where ingestion_time() >= TimeWindow
            | where metric in ("Executor Efficiency", "GC Overhead", "Application Duration (sec)", "Executor Count")
            | summarize arg_max(value, *) by app_id, metric
            | extend 
                executor_efficiency = iff(metric == "Executor Efficiency", value, 0.0),
                gc_overhead = iff(metric == "GC Overhead", value, 0.0),
                duration_sec = iff(metric == "Application Duration (sec)", value, 0.0),
                executor_count = iff(metric == "Executor Count", value, 0.0)
            | summarize 
                executor_efficiency = max(executor_efficiency),
                gc_overhead = max(gc_overhead),
                duration_sec = max(duration_sec),
                executor_count = max(executor_count)
            by app_id
        ) on app_id
        | extend 
            health_status = case(
                gc_overhead > 0.4 or executor_efficiency < 0.3, "CRITICAL",
                gc_overhead > 0.25 or executor_efficiency < 0.5, "WARNING",
                "HEALTHY"
            ),
            duration_min = round(duration_sec / 60.0, 2)
        | project 
            app_id,
            app_name = coalesce(app_name, "Unknown"),
            artifact_id = coalesce(artifact_id, "Unknown"),
            health_status = coalesce(health_status, "UNKNOWN"),
            duration_min = coalesce(duration_min, 0.0),
            executor_efficiency = coalesce(executor_efficiency, 0.0),
            gc_overhead_pct = coalesce(gc_overhead * 100, 0.0)
        | order by duration_min desc
        """
        return self.query_to_dict_list(query)
    
    def get_application_summary(self, application_id: str) -> Dict[str, Any]:
        """
        Get comprehensive application health summary with joined metrics.
        
        Args:
            application_id: The Spark application ID
            
        Returns:
            Health summary with executor failures, shuffle spills, GC overhead, skew
        """
        query = f"""
        let AppMetrics = sparklens_metrics
        | where app_id == '{application_id}'
        | summarize arg_max(value, *) by metric
        | project metric, value
        | summarize 
            executor_efficiency = maxif(value, metric == "Executor Efficiency"),
            gc_overhead = maxif(value, metric == "GC Overhead"),
            task_skew = maxif(value, metric == "Task Skew Ratio"),
            parallelism_score = maxif(value, metric == "Parallelism Score"),
            duration_sec = maxif(value, metric == "Application Duration (sec)"),
            executor_count = maxif(value, metric == "Executor Count");
        let AppMeta = sparklens_metadata
        | where applicationId == '{application_id}'
        | project 
            app_name = applicationName,
            executor_max = executorMax,
            executor_min = executorMin,
            high_concurrency = isHighConcurrencyEnabled
        | take 1;
        AppMetrics
        | extend 
            app_id = '{application_id}',
            health_status = case(
                gc_overhead > 0.4 or task_skew > 5.0 or executor_efficiency < 0.3, "CRITICAL",
                gc_overhead > 0.25 or task_skew > 3.0 or executor_efficiency < 0.5, "WARNING",
                "HEALTHY"
            ),
            performance_grade = case(
                executor_efficiency > 0.7 and gc_overhead < 0.15 and task_skew < 2.0, "A",
                executor_efficiency > 0.5 and gc_overhead < 0.25 and task_skew < 3.0, "B",
                executor_efficiency > 0.3 and gc_overhead < 0.35, "C",
                "D"
            ),
            gc_overhead_pct = gc_overhead * 100,
            task_skew_ratio = task_skew
        | extend dummy = 1
        | join kind=leftouter (AppMeta | extend dummy = 1) on dummy
        | project 
            app_id,
            app_name = coalesce(app_name, "Unknown"),
            health_status,
            performance_grade,
            duration_sec = coalesce(duration_sec, 0.0),
            executor_count = coalesce(executor_count, 0.0),
            executor_efficiency = coalesce(executor_efficiency, 0.0),
            gc_overhead_pct,
            task_skew_ratio = coalesce(task_skew_ratio, 1.0),
            parallelism_score = coalesce(parallelism_score, 0.0),
            executor_config = strcat("Min:", executor_min, " Max:", executor_max),
            high_concurrency = coalesce(high_concurrency, false)
        """
        results = self.query_to_dict_list(query)
        return results[0] if results else {
            "app_id": application_id,
            "health_status": "NOT_FOUND",
            "error": "Application not found in database"
        }
    
    def get_fabric_recommendations(self, application_id: str) -> List[Dict[str, Any]]:
        """
        Get Microsoft Fabric-specific optimization recommendations for an application.
        
        These recommendations cover:
        - Native Execution Engine (NEE) enablement
        - High Concurrency mode settings
        - Delta Lake best practices (Auto Compaction, V-Order, etc.)
        - Resource profile optimization
        - Fabric-specific configuration tuning
        
        Args:
            application_id: The Spark application ID
            
        Returns:
            List of Fabric-specific recommendation records
        """
        query = f"""
        fabric_recommedations
        | where app_id == '{application_id}'
        | project 
            app_id,
            recommendation,
            timestamp = now()
        | order by app_id asc
        """
        return self.query_to_dict_list(query)
    
    def search_recommendations_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Search recommendations by category keyword.
        
        Args:
            category: Category keyword (memory, shuffle, join, cpu, gc, skew, etc.)
            
        Returns:
            Filtered recommendations matching the category
        """
        # Map common categories to search patterns
        category_patterns = {
            "memory": ["Memory", "GC", "heap", "cache"],
            "shuffle": ["Shuffle", "partition", "repartition"],
            "join": ["Join", "broadcast", "skew"],
            "cpu": ["CPU", "Efficiency", "executor"],
            "gc": ["GC", "Garbage Collection"],
            "skew": ["Skew", "imbalance", "straggler"],
            "driver": ["Driver", "coordination"],
            "parallelism": ["Parallelism", "task", "core"],
            "streaming": ["Streaming", "micro-batch"],
            "fabric": ["Fabric", "NEE", "Native Execution"]
        }
        
        # Get search pattern
        search_terms = category_patterns.get(category.lower(), [category])
        search_filter = " or ".join([f"recommendation has '{term}'" for term in search_terms])
        
        query = f"""
        union isfuzzy=true
        (
            sparklens_recommedations
            | where {search_filter}
            | project 
                app_id,
                source = "sparklens",
                recommendation,
                category = '{category}'
        ),
        (
            fabric_recommedations
            | where {search_filter}
            | project 
                app_id,
                source = "fabric",
                recommendation,
                category = '{category}'
        )
        | order by app_id asc
        | take 100
        """
        return self.query_to_dict_list(query)    
    def get_application_metrics(self, application_id: str) -> Dict[str, Any]:
        """
        Get key performance metrics for an application - use this FIRST to assess severity.
        
        Returns metrics with severity thresholds:
        - Executor Efficiency: <0.3 = CRITICAL, <0.4 = HIGH
        - GC Overhead: >0.4 = CRITICAL, >0.25 = HIGH
        - Task Skew: >10x = CRITICAL, >5x = HIGH
        - Parallelism Score: <0.4 = MEDIUM
        - Job Type: 1.0=STREAMING, 0.0=BATCH
        
        Args:
            application_id: The Spark application ID
            
        Returns:
            Dictionary with all metrics and calculated performance score
        """
        query = f"""
        let Metrics = sparklens_metrics
        | where app_id == '{application_id}'
        | summarize arg_max(value, *) by metric
        | project metric, value;
        Metrics
        | summarize 
            executor_efficiency = maxif(value, metric == "Executor Efficiency"),
            gc_overhead = maxif(value, metric == "GC Overhead"),
            task_skew_ratio = maxif(value, metric == "Task Skew Ratio"),
            parallelism_score = maxif(value, metric == "Parallelism Score"),
            job_type = maxif(value, metric == "Job Type"),
            driver_time_pct = maxif(value, metric == "Driver Time %"),
            executor_time_pct = maxif(value, metric == "Executor Time %"),
            duration_sec = maxif(value, metric == "Application Duration (sec)"),
            executor_count = maxif(value, metric == "Executor Count"),
            task_count = maxif(value, metric == "Task Count")
        | extend 
            app_id = '{application_id}',
            job_type_label = iff(job_type >= 0.5, "STREAMING", "BATCH"),
            performance_score = (executor_efficiency * 30) + (parallelism_score * 30) + 
                               ((1.0 - gc_overhead) * 20) + ((1.0 / task_skew_ratio) * 20),
            severity = case(
                executor_efficiency < 0.2 or gc_overhead > 0.4 or driver_time_pct > 80 or task_skew_ratio > 10, "CRITICAL",
                executor_efficiency < 0.4 or gc_overhead > 0.25 or task_skew_ratio > 5, "HIGH",
                parallelism_score < 0.4, "MEDIUM",
                "LOW"
            )
        | extend
            grade = case(
                performance_score >= 80, "EXCELLENT",
                performance_score >= 65, "GOOD",
                performance_score >= 50, "FAIR",
                "POOR"
            )
        | project 
            app_id,
            job_type_label,
            severity,
            grade,
            performance_score,
            executor_efficiency,
            gc_overhead,
            task_skew_ratio,
            parallelism_score,
            driver_time_pct,
            executor_time_pct,
            duration_sec,
            executor_count,
            task_count
        """
        results = self.query_to_dict_list(query)
        return results[0] if results else {
            "app_id": application_id,
            "error": "No metrics found for this application"
        }
    
    def get_scaling_predictions(self, application_id: str) -> List[Dict[str, Any]]:
        """
        Get executor scaling impact predictions.
        
        Shows different executor multipliers and their predicted impact.
        
        Args:
            application_id: The Spark application ID
            
        Returns:
            List of predictions for different executor counts
        """
        query = f"""
        sparklens_predictions
        | where app_id == '{application_id}'
        | project 
            app_id,
            executor_count = [\"Executor Count\"],
            executor_multiplier = [\"Executor Multiplier\"],
            estimated_wallclock = [\"Estimated Executor WallClock\"],
            estimated_duration = [\"Estimated Total Duration\"]
        | order by executor_count asc
        """
        return self.query_to_dict_list(query)
    
    def get_application_metadata(self, application_id: str) -> Dict[str, Any]:
        """
        Get application configuration metadata and Fabric settings.
        
        Returns all configuration properties including NEE, VOrder, resource profiles, etc.
        
        Args:
            application_id: The Spark application ID
            
        Returns:
            Dictionary with configuration metadata
        """
        query = f"""
        sparklens_metadata
        | where applicationId == '{application_id}'
        | project 
            app_id = applicationId,
            app_name = applicationName,
            artifact_id = artifactId,
            artifact_type = artifactType,
            capacity_id = capacityId,
            executor_max = executorMax,
            executor_min = executorMin,
            high_concurrency_enabled = isHighConcurrencyEnabled,
            native_execution_enabled = [\"spark.native.enabled\"],
            auto_compact = [\"spark.databricks.delta.autoCompact.enabled\"],
            adaptive_file_size = [\"spark.microsoft.delta.targetFileSize.adaptive.enabled\"],
            fast_optimize = [\"spark.microsoft.delta.optimize.fast.enabled\"],
            file_level_compaction = [\"spark.microsoft.delta.optimize.fileLevelTarget.enabled\"],
            extended_stats = [\"spark.microsoft.delta.stats.collect.extended\"],
            snapshot_acceleration = [\"spark.microsoft.delta.snapshot.driverMode.enabled\"],
            vorder = [\"spark.sql.parquet.vorder.default\"],
            optimize_write = [\"spark.microsoft.delta.optimizeWrite.enabled\"],
            resource_profile = [\"spark.fabric.resourceProfile\"]
        """
        results = self.query_to_dict_list(query)
        return results[0] if results else {
            "app_id": application_id,
            "error": "No metadata found for this application"
        }
    
    def get_stage_summary(self, application_id: str, stage_id: int = None) -> List[Dict[str, Any]]:
        """
        Get detailed stage-level task statistics.
        
        Args:
            application_id: The Spark application ID
            stage_id: Optional specific stage ID to filter
            
        Returns:
            List of stage statistics
        """
        stage_filter = f"and stage_id == {stage_id}" if stage_id is not None else ""
        
        query = f"""
        sparklens_summary
        | where app_id == '{application_id}' {stage_filter}
        | project 
            app_id,
            stage_id,
            stage_attempt_id,
            num_tasks,
            successful_tasks,
            failed_tasks,
            min_duration_sec,
            max_duration_sec,
            avg_duration_sec,
            p75_duration_sec,
            avg_shuffle_read_mb,
            max_shuffle_read_mb,
            avg_shuffle_write_mb,
            max_shuffle_write_mb,
            avg_input_mb,
            max_input_mb,
            avg_output_mb,
            max_output_mb,
            num_executors,
            stage_execution_time_sec
        | extend 
            task_imbalance = iff(avg_duration_sec > 0, max_duration_sec / avg_duration_sec, 1.0),
            shuffle_imbalance = iff(avg_shuffle_read_mb > 0, max_shuffle_read_mb / avg_shuffle_read_mb, 1.0)
        | order by stage_id asc
        """
        return self.query_to_dict_list(query)
    
    def get_database_schema(self) -> Dict[str, Any]:
        """
        Discover all tables and their columns in the database for LLM-powered queries.
        
        Returns:
            Dictionary with table names as keys and column info as values
        """
        # Simplified query - we're already connected to the specific database
        # No need to filter by DatabaseName since .show database schema returns only current DB
        query = """
        .show database schema
        | project TableName, ColumnName, ColumnType
        | order by TableName asc, ColumnName asc
        """
        
        results = self.query_to_dict_list(query)
        
        # Group by table name
        schema = {}
        for row in results:
            table_name = row.get("TableName", "")
            column_name = row.get("ColumnName", "")
            column_type = row.get("ColumnType", "")
            
            if table_name not in schema:
                schema[table_name] = []
            
            schema[table_name].append({
                "name": column_name,
                "type": column_type
            })
        
        return schema
    
    def validate_query_safety(self, query: str) -> tuple[bool, str]:
        """
        Validate that a KQL query is safe to execute (read-only).
        
        Args:
            query: The KQL query to validate
            
        Returns:
            Tuple of (is_safe, error_message)
        """
        query_lower = query.lower().strip()
        
        # Check for dangerous commands
        dangerous_commands = [
            ".drop", ".delete", ".clear", ".purge", ".alter",
            ".create", ".set", ".append", ".move", ".rename",
            ".replace", "drop table", "drop database", "truncate"
        ]
        
        for cmd in dangerous_commands:
            if cmd in query_lower:
                return False, f"Query contains forbidden command: {cmd}"
        
        # Must be a read query (starts with table name or .show)
        if not (query_lower.startswith(".show") or 
                any(table in query_lower for table in ["sparklens_", "fabric_"])):
            return False, "Query must start with a table name or .show command"
        
        return True, ""
    
    def execute_dynamic_query(self, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Execute a dynamically generated KQL query with safety checks.
        
        Args:
            query: The KQL query to execute
            max_results: Maximum number of results to return
            
        Returns:
            List of result dictionaries
        """
        # Validate query safety
        is_safe, error_msg = self.validate_query_safety(query)
        if not is_safe:
            raise ValueError(f"Query validation failed: {error_msg}")
        
        # Add limit if not present
        if "take" not in query.lower() and "limit" not in query.lower():
            query = f"{query}\n| take {max_results}"
        
        try:
            return self.query_to_dict_list(query)
        except Exception as e:
            raise ValueError(f"Query execution failed: {str(e)}")
    
    def insert_feedback(
        self,
        session_id: str,
        application_id: str,
        query_text: str,
        query_intent: str,
        actual_result_generated: str,
        feedback_type: str,
        feedback_comment: str = "",
        recommendation_count: int = 0,
        source_kusto_count: int = 0,
        source_rag_count: int = 0,
        source_llm_count: int = 0
    ) -> bool:
        """
        Insert user feedback into sparkagent_feedback table.
        
        Args:
            session_id: Unique session identifier
            application_id: Spark application ID (or "N/A" for general queries)
            query_text: User's original question
            query_intent: Detected intent (analyze_app, show_bad_apps, general_chat, etc.)
            actual_result_generated: Full response text shown to user
            feedback_type: HELPFUL, NOT_HELPFUL, or PARTIAL
            feedback_comment: User's optional comment
            recommendation_count: Number of recommendations shown
            source_kusto_count: How many recommendations from Kusto
            source_rag_count: How many from RAG
            source_llm_count: How many from LLM
            
        Returns:
            True if successful, False otherwise
        """
        from datetime import datetime
        import json
        
        try:
            # Escape strings for KQL (replace single quotes with double single quotes)
            def escape_kql(s: str) -> str:
                if s is None:
                    return ""
                # Truncate very long strings
                if len(s) > 10000:
                    s = s[:10000] + "... [truncated]"
                return s.replace("'", "''")
            
            timestamp = datetime.utcnow().isoformat()
            
            # Build KQL insert command using .set-or-append with datatable
            query = f"""
.set-or-append sparkagent_feedback <| datatable(
    timestamp:datetime,
    session_id:string,
    application_id:string,
    query_text:string,
    query_intent:string,
    actual_result_generated:string,
    feedback_type:string,
    feedback_comment:string,
    recommendation_count:int,
    source_kusto_count:int,
    source_rag_count:int,
    source_llm_count:int
)
[
    datetime('{timestamp}'),
    '{escape_kql(session_id)}',
    '{escape_kql(application_id)}',
    '{escape_kql(query_text)}',
    '{escape_kql(query_intent)}',
    '{escape_kql(actual_result_generated)}',
    '{escape_kql(feedback_type)}',
    '{escape_kql(feedback_comment)}',
    {recommendation_count},
    {source_kusto_count},
    {source_rag_count},
    {source_llm_count}
]
"""
            
            # Execute the insert command
            self.client.execute(self.database, query)
            print(f"✅ Feedback saved: {feedback_type} for {query_intent}")
            return True
            
        except Exception as e:
            print(f"⚠️ Failed to save feedback: {e}")
            # Don't crash the app if feedback fails - just log it
            return False