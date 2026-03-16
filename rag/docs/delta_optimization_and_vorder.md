# Optimize Delta Lake tables with V-Order

Source: https://learn.microsoft.com/en-us/fabric/data-engineering/delta-optimization-and-v-order

The Lakehouse and Delta Lake table format are central to Microsoft Fabric. Keeping Delta tables optimized is key to performance and cost efficiency for analytics workloads.

## What is V-Order?

V-Order is a write-time optimization for Parquet files that can improve downstream query performance across Fabric engines.

**At a glance:**

- **Where it helps most:** Read-heavy patterns such as dashboarding, interactive analytics, and repeated scans.
- **How it helps:** Reorganizes Parquet layout (row-group distribution, encoding, and compression) to improve read efficiency.
- **Typical tradeoff:** Writes might take longer (often around 15% on average), while reads can improve significantly depending on workload.
- **Engine compatibility:** Files remain open-source Parquet compliant. Delta features such as Z-Order remain compatible.
- **Scope:** V-Order is file-level. Delta operations such as compaction, vacuum, and time travel can be used with it.

## V-Order Default Behavior

V-Order is **disabled by default** in new Fabric workspaces (`spark.sql.parquet.vorder.default=false`) to improve write performance for ingestion and transformation pipelines.

For read-heavy workloads such as interactive queries or dashboarding, enable V-Order by setting `spark.sql.parquet.vorder.default` to `true`. You can also switch to `readHeavyforSpark` or `ReadHeavy` resource profiles, which automatically enable V-Order for read-focused performance.

## V-Order vs Z-Order

- **Z-Order** (`ZORDER`) clusters related values together to improve data skipping for selective filters.
- **V-Order** (`VORDER`) optimizes Parquet file layout to improve read efficiency across Fabric engines.

Quick decision guide:
- Use `VORDER` when you want broad read-performance improvements across engines.
- Use `ZORDER BY (...)` with `VORDER` when queries repeatedly filter on known columns and you also want the V-Order layout benefits.
- Both can be combined: `OPTIMIZE table ZORDER BY (col1) VORDER;`

## Configuration Properties

| Property | Default | Scope |
|---|---|---|
| `spark.sql.parquet.vorder.default` | `false` | Session-level V-Order writing |
| `TBLPROPERTIES("delta.parquet.vorder.enabled")` | Unset | Table-level default |
| DataFrame writer option: `parquet.vorder.enabled` | Unset | Per write-operation control |

## Control V-Order at Session Level

Check current session value:
```sql
%%sql
SET spark.sql.parquet.vorder.default
```

Enable V-Order for the session (read-heavy workloads):
```sql
%%sql
SET spark.sql.parquet.vorder.default=TRUE
```

Disable V-Order for the session (write-heavy / ingestion workloads):
```sql
%%sql
SET spark.sql.parquet.vorder.default=FALSE
```

**Note:** When enabled at session level, all Parquet writes in that session use V-Order, including non-Delta Parquet tables.

## Control V-Order at Table Level

Enable V-Order during table creation:
```sql
%%sql
CREATE TABLE person (id INT, name STRING, age INT)
USING parquet
TBLPROPERTIES("delta.parquet.vorder.enabled" = "true");
```

Enable or disable on existing table:
```sql
%%sql
ALTER TABLE person SET TBLPROPERTIES("delta.parquet.vorder.enabled" = "true");
ALTER TABLE person SET TBLPROPERTIES("delta.parquet.vorder.enabled" = "false");
ALTER TABLE person UNSET TBLPROPERTIES("delta.parquet.vorder.enabled");
```

Table property only affects future writes. To retroactively apply V-Order to existing files, use OPTIMIZE VORDER.

## Control V-Order at Write Level (PySpark)

Write with V-Order explicitly enabled:
```python
df_source.write \
  .format("delta") \
  .mode("append") \
  .option("parquet.vorder.enabled", "true") \
  .saveAsTable("myschema.mytable")
```

## Apply V-Order During OPTIMIZE (Delta Table Maintenance)

Compact and apply V-Order in a single operation:
```sql
%%sql
OPTIMIZE <table_or_path> VORDER;

OPTIMIZE <table_or_path> WHERE <predicate> VORDER;

OPTIMIZE <table_or_path> WHERE <predicate> ZORDER BY (col1, col2) VORDER;
```

When ZORDER and VORDER are used together, Spark applies: bin compaction → Z-Order → V-Order.

## What is Optimize Write?

Optimize Write is a Delta Lake feature in Fabric that reduces file count and increases individual file size during writes in Apache Spark. It solves the small file problem common in batch and streaming ingestion. It is **enabled by default** in Microsoft Fabric Runtime.

## Merge Optimization (Low Shuffle Merge)

Delta Lake MERGE in Fabric runtime includes Low Shuffle Merge optimization to reduce overhead on unchanged rows.

Controlled by: `spark.microsoft.delta.merge.lowShuffle.enabled` (enabled by default).
No code changes required. Compatible with open-source Delta Lake.

## Delta Table Maintenance Best Practices

| Operation | Purpose |
|---|---|
| `OPTIMIZE` | Bin compaction — consolidates small files into larger Parquet files |
| `OPTIMIZE VORDER` | Compaction + V-Order layout rewrite in one pass |
| `VACUUM` | Removes dereferenced files; default retention is 7 days (168 hours) |

VACUUM example:
```sql
%%sql
VACUUM schema_name.table_name;
VACUUM schema_name.table_name RETAIN 168 HOURS;
```

**Important:** OPTIMIZE and VACUUM are Spark SQL commands. Run them in Fabric notebooks or Spark job definitions — not in the SQL Analytics Endpoint or Warehouse SQL query editor.

## Migration Note (Runtime 1.3+)

In Fabric runtime 1.3 and later, `spark.sql.parquet.vorder.enable` (without the `.default` suffix) is removed. V-Order can now be applied automatically during Delta optimization with OPTIMIZE. Remove the old setting from any existing code.

## Related Links

- https://learn.microsoft.com/en-us/fabric/data-engineering/configure-resource-profile-configurations
- https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-table-maintenance
- https://learn.microsoft.com/en-us/fabric/fundamentals/table-maintenance-optimization
