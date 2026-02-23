# Configure Resource Profile Configurations in Microsoft Fabric

Microsoft Fabric now supports predefined Spark resource profiles—a simple and powerful way for data engineers to optimize Spark configurations based on workload needs. These profiles enable users to quickly apply tuning best practices for common patterns like read-heavy, write-heavy, or hybrid workloads using a property bag-based approach.

Whether you're ingesting terabytes of streaming data or running high-performance analytics queries, resource profiles provide a fast path to performance without requiring manual Spark tuning.

## Benefits of Resource Profiles

- ✅ **Performance by default** – Apply proven, workload-optimized Spark settings out of the box
- ✅ **Flexibility** – Choose or customize profiles based on your ingestion and query patterns
- ✅ **Fine-tuned Spark configs** – Avoid trial-and-error tuning and reduce operational overhead

> **Note**: All new Fabric workspaces are now defaulted to the `writeHeavy` profile for optimal ingestion performance. This includes default configurations tailored for large-scale ETL and streaming data workflows. If the writeHeavy profile is used, VOrder is disabled by default and must be manually enabled.

## Available Resource Profiles

| Profile | Description | Configuration |
|---------|-------------|---------------|
| **readHeavyForSpark** | Optimized for Spark workloads with frequent reads | `spark.fabric.resourceProfile = readHeavyForSpark` |
| **readHeavyForPBI** | Optimized for Power BI queries on Delta tables | `spark.fabric.resourceProfile = readHeavyForPBI` |
| **writeHeavy** | Optimized for high-frequency ingestion & writes | `spark.fabric.resourceProfile = writeHeavy` |
| **custom** | Fully user-defined configuration | `spark.fabric.resourceProfile = custom` |

## Default Configuration Values for Each Profile

### writeHeavy Profile
```json
{
  "spark.sql.parquet.vorder.default": "false",
  "spark.databricks.delta.optimizeWrite.enabled": "null",
  "spark.databricks.delta.optimizeWrite.binSize": "128",
  "spark.databricks.delta.optimizeWrite.partitioned.enabled": "true"
}
```

### readHeavyForPBI Profile
```json
{
  "spark.sql.parquet.vorder.default": "true",
  "spark.databricks.delta.optimizeWrite.enabled": "true",
  "spark.databricks.delta.optimizeWrite.binSize": "1g"
}
```

### readHeavyForSpark Profile
```json
{
  "spark.databricks.delta.optimizeWrite.enabled": "true",
  "spark.databricks.delta.optimizeWrite.partitioned.enabled": "true",
  "spark.databricks.delta.optimizeWrite.binSize": "128"
}
```

### custom Profile Example
```json
{
  "spark.sql.shuffle.partitions": "800",
  "spark.sql.adaptive.enabled": "true",
  "spark.serializer": "org.apache.spark.serializer.KryoSerializer"
}
```

> **Tip**: You can name your custom profile with a meaningful name that reflects your workload pattern, like `fastIngestProfile` or `lowLatencyAnalytics`.

## How to Configure Resource Profiles

### 1. Configuring Resource Profiles Using Environments

You can define the default Spark resource profile at the environment level. When applied, the selected profile will automatically be used for all Spark jobs within the environment unless overridden.

**Steps:**
1. Navigate to your Fabric workspace
2. Edit or create a new environment
3. Under Spark Configurations, set: `spark.fabric.resourceProfile = writeHeavy` (or readHeavyForPBI, readHeavyForSpark, or your own custom name)
4. You can choose an existing profile and also modify the default values (e.g., choose readHeavyForSpark and increase binsize from 128 to 256)

### 2. Configuring Resource Profiles at Runtime with spark.conf.set

You can also override the default resource profile during notebook execution or Spark job runs using:

```python
spark.conf.set("spark.fabric.resourceProfile", "readHeavyForSpark")
```

This approach provides runtime flexibility to change behavior based on job logic, schedule, or workload type—allowing different profiles for different parts of a notebook.

> **Note**: If both environment and runtime configurations are set, runtime settings take precedence.

## What Happens by Default?

All newly created workspaces in Microsoft Fabric default to the `writeHeavy` profile. This ensures:

- Efficient handling of data ingestion pipelines
- Optimized throughput for batch and streaming jobs
- Better out-of-the-box performance for common ETL workloads

If your workload differs (e.g., interactive queries, dashboard serving), you can update the default settings at the environment level or override them dynamically during execution.

> ⚠️ **Important**: On all new Fabric workspaces, VOrder is disabled by default (`spark.sql.parquet.vorder.default=false`). This default configuration is optimized for write-heavy data engineering workloads, enabling greater performance during ingestion and transformation at scale.

For read-optimized scenarios (e.g., Power BI dashboards or interactive Spark queries), consider switching to the `readHeavyforSpark` or `readHeavyForPBI` resource profiles or modify the properties by enabling VOrder to improve query performance from PowerBI and Datawarehouse workloads.
