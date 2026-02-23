# Use Table Maintenance Feature to Manage Delta Tables in Fabric

The Lakehouse in Microsoft Fabric provides the Table maintenance feature to efficiently manage delta tables and to keep them always ready for analytics. This guide describes the table maintenance feature in Lakehouse and its capabilities.

> **Tip**: For comprehensive cross-workload guidance on table maintenance strategies, including optimization recommendations for SQL analytics endpoint, Power BI Direct Lake, and Data Warehouse consumers, see Cross-workload table maintenance and optimization.

## Key Capabilities

- Perform ad hoc table maintenance using contextual right-click actions in a delta table within the Lakehouse explorer
- Apply bin-compaction, V-Order, and unreferenced old files cleanup

> **Note**: For advanced maintenance tasks, such as grouping multiple table maintenance commands, orchestrating it based on a schedule, a code-centric approach is the recommended choice. You can also use the Lakehouse API to automate table maintenance operations.

## Supported File Types

Lakehouse table maintenance applies only to **Delta Lake tables**. The legacy Hive tables that use PARQUET, ORC, AVRO, CSV, and other formats aren't supported.

## Table Maintenance Operations

The table maintenance feature offers three operations:

### 1. Optimize

Consolidates multiple small Parquet files into larger files. Big Data processing engines, and all Fabric engines, benefit from having larger file sizes. Having files of size above **128 MB**, and optimally close to **1 GB**, improves compression and data distribution across the cluster nodes.

**Benefits:**
- Reduces the need to scan numerous small files for efficient read operations
- Improves query performance
- Better compression ratios

**Best Practice:** It's a general best practice to run optimization strategies after loading large tables.

### 2. V-Order

Applies optimized sorting, encoding, and compression to Delta parquet files to enable fast read operations across all the Fabric engines. V-Order happens during the optimize command, and is presented as an option to the command group in the user experience.

**Key Features:**
- Optimized sorting for better data locality
- Efficient encoding schemes
- Advanced compression algorithms
- Fast read performance across Power BI, SQL, and Spark

### 3. Vacuum

Removes old files no longer referenced by a Delta table log. Files need to be older than the retention threshold.

**Default Settings:**
- Default file retention threshold: **7 days**
- All delta tables in OneLake have the same retention period
- File retention period is same regardless of the Fabric compute engine you are using

> **Important**: Setting a shorter retention period impacts Delta's time travel capabilities. It's a general best practice to set a retention interval to at least seven days, because old snapshots and uncommitted files can still be in use by concurrent table readers and writers.

**Safety Note:** Cleaning up active files with the VACUUM command might lead to reader failures or even table corruption if uncommitted files are removed. Table maintenance experiences in the user interface and in the Public APIs will fail by default when intervals are less than 7 days.

**Override for Lower Retention:**
To force lower retention intervals for the vacuum command, configure:
```python
spark.conf.set("spark.databricks.delta.retentionDurationCheck.enabled", "false")
```

Table Maintenance jobs will then pick up the configuration and allow the lower retention during the job execution.

## Execute Ad Hoc Table Maintenance

### How to use the feature:

1. From your Microsoft Fabric account, navigate to the desired Lakehouse
2. From the Lakehouse explorer's **Tables** section, either right-click on the table or use the ellipsis to access the contextual menu
3. Select the **Maintenance** menu entry
4. Check the maintenance options in the dialog per your requirement
5. Select **Run now** to execute the table maintenance job
6. Track maintenance job execution by the notifications pane, or the Monitoring Hub

## How Does Table Maintenance Work?

After **Run now** is selected, a Spark maintenance job is submitted for execution:

1. The Spark job is submitted using the user identity and table privileges
2. The Spark job consumes Fabric capacity of the workspace/user that submitted the job
3. If there is another maintenance job running on a table, a new one is rejected
4. Jobs on different tables can execute in parallel
5. Table maintenance jobs can be easily tracked in the **Monitoring Hub** - Look for "TableMaintenance" text within the activity name column

## Retention Best Practices

| Retention Period | Use Case | Risk Level |
|-----------------|----------|------------|
| 7+ days | Production tables, time travel needed | ✅ Safe |
| 3-6 days | Development/test environments | ⚠️ Medium risk |
| < 3 days | Temporary tables only | ❌ High risk |

## Performance Impact

| Operation | CPU Impact | Storage Impact | Duration |
|-----------|-----------|----------------|----------|
| Optimize | Medium-High | Temporary increase | Minutes to hours |
| V-Order | High | Same as Optimize | Same as Optimize |
| Vacuum | Low | Decreases | Fast |

## Recommended Maintenance Schedule

- **Optimize + V-Order**: After bulk ingestion or weekly for active tables
- **Vacuum**: Weekly or monthly depending on retention requirements
