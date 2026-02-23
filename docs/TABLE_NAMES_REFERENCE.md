# ✅ Table Name Reference - Orchestrator vs Kusto

**Review Date:** 2026-02-22  
**Status:** All table names verified and consistent

---

## 📋 **Summary**

All table names used in the orchestrator match exactly with the KustoClient implementation. The code is **internally consistent**.

**⚠️ Important Note:** Table names use intentional misspelling `recommedations` (missing 'n') - this must match your analyzer code that writes to Kusto.

---

## 🗂️ **Table Names Used**

### **1. sparklens_recommedations** ⚠️ Note spelling
**Purpose:** SparkLens analysis recommendations  
**Schema:** `app_id`, `recommendation`, `severity`, `category`, `timestamp`

**Used in:**
- ✅ `kusto_client.py` - Line 138 (query)
- ✅ `kusto_client.py` - Line 380 (search by category)
- ✅ `orchestrator.py` - Line 410 (LLM prompt schema)
- ✅ `orchestrator.py` - Lines 433-439 (query examples)
- ✅ `orchestrator.py` - Line 490 (query validation)
- ✅ `orchestrator.py` - Line 673 (list apps query)
- ✅ `orchestrator.py` - Lines 700, 705 (error messages)

**Column accessed:** `recommendation` (singular)

---

### **2. fabric_recommedations** ⚠️ Note spelling
**Purpose:** Microsoft Fabric-specific recommendations  
**Schema:** `app_id`, `recommendation`, `severity`, `category`, `timestamp`

**Used in:**
- ✅ `kusto_client.py` - Line 339 (query)
- ✅ `kusto_client.py` - Line 389 (search by category)
- ✅ `orchestrator.py` - Line 412 (LLM prompt schema)
- ✅ `orchestrator.py` - Line 490 (query validation)

**Column accessed:** `recommendation` (singular)

---

### **3. sparklens_metrics**
**Purpose:** Application performance metrics  
**Schema:** `app_id` (or `application_id`), `metric`, `value`, `timestamp`

**Key metrics:**
- `Application Duration (sec)` ← Use for slowest apps
- `Total Executor Time (sec)`
- `Executor Efficiency`
- `GC Overhead`
- `Task Skew Ratio`
- `Parallelism Score`
- `Driver Time %`
- `Job Type` (1.0 = streaming, 0.0 = batch)

**Used in:**
- ✅ `kusto_client.py` - Line 160 (bad practices)
- ✅ `kusto_client.py` - Line 213 (recent apps)
- ✅ `kusto_client.py` - Line 259 (app summary)
- ✅ `kusto_client.py` - Line 419 (app metrics)
- ✅ `orchestrator.py` - Line 409 (LLM prompt schema)
- ✅ `orchestrator.py` - Line 420 (slowest apps example)
- ✅ `orchestrator.py` - Line 490 (query validation)
- ✅ `orchestrator.py` - Line 620 (top N apps query)

**Column field name:** `application_id` (in some queries) or `app_id`

---

### **4. sparklens_metadata**
**Purpose:** Spark configuration properties  
**Schema:** `app_id` (or `application_id`), `property_name`, `property_value`, `timestamp`

**Used in:**
- ✅ `kusto_client.py` - Line 182 (bad practices config check)
- ✅ `kusto_client.py` - Line 207 (recent apps)
- ✅ `kusto_client.py` - Line 263 (app summary)
- ✅ `kusto_client.py` - Line 512 (app metadata)
- ✅ `orchestrator.py` - Line 413 (LLM prompt schema)
- ✅ `orchestrator.py` - Line 442 (metadata query example)
- ✅ `orchestrator.py` - Line 490 (query validation)

**Column field name:** `application_id` (in queries) or `app_id`

---

### **5. sparklens_predictions**
**Purpose:** Scaling predictions and what-if scenarios  
**Schema:** `app_id`, `current_executors`, `predicted_executors`, `predicted_time`, `confidence`, `timestamp`

**Used in:**
- ✅ `kusto_client.py` - Line 487 (scaling predictions query)

---

### **6. sparklens_summary**
**Purpose:** Stage-level execution summary  
**Schema:** `app_id`, `stage_id`, `stage_duration`, `task_count`, `data_read`, `data_written`, `timestamp`

**Used in:**
- ✅ `kusto_client.py` - Line 554 (stage summary query)

---

### **7. sparkagent_feedback**
**Purpose:** User feedback for continuous learning  
**Schema defined in:** `mcp_server/sparkagent_feedback_schema.kql`

**Fields:**
- `timestamp`, `session_id`, `application_id`, `query_text`, `query_intent`
- `actual_result_generated`, `feedback_type`, `feedback_comment`
- `recommendation_count`, `source_kusto_count`, `source_rag_count`, `source_llm_count`

**Used in:**
- ✅ `kusto_client.py` - Line 688 (insert_feedback method)
- ✅ `kusto_client.py` - Line 723 (.set-or-append query)

---

## ⚠️ **Critical: Column Name Consistency**

### **Field name variations found:**

| Table | Field in Code | Actual Query Uses |
|-------|---------------|-------------------|
| sparklens_metrics | `app_id` | `application_id` |
| sparklens_metadata | `app_id` | `application_id` |
| sparklens_summary | `app_id` | `application_id` |
| sparklens_recommedations | `app_id` | `app_id` |
| fabric_recommedations | `app_id` | `app_id` |

**✅ This is handled correctly** - KustoClient queries use the right column names.

---

## 🔍 **What to Verify in Your Analyzer Code**

When you ingest data from your analyzer (Notebook/PySpark script), ensure these exact table names and spellings:

### ✅ **Checklist:**

```python
# Example: What your analyzer should write to
# (adjust based on your actual analyzer implementation)

# 1. Recommendations table (note the spelling!)
spark.sql(f"""
    INSERT INTO sparklens_recommedations  -- NOT "recommendations"
    VALUES ('{app_id}', '{recommendation_text}', '{severity}', '{category}', current_timestamp())
""")

# 2. Fabric recommendations (same spelling!)
spark.sql(f"""
    INSERT INTO fabric_recommedations  -- NOT "recommendations"
    VALUES ('{app_id}', '{recommendation_text}', '{severity}', '{category}', current_timestamp())
""")

# 3. Metrics table (use "application_id" not "app_id")
spark.sql(f"""
    INSERT INTO sparklens_metrics
    VALUES ('{application_id}', '{metric_name}', {value}, current_timestamp())
""")

# 4. Metadata table (use "application_id" not "app_id")
spark.sql(f"""
    INSERT INTO sparklens_metadata
    VALUES ('{application_id}', '{property_name}', '{property_value}', current_timestamp())
""")
```

---

## 🛠️ **Recommendations**

### **If analyzer uses different table names:**

1. **Option A (Recommended):** Update analyzer to match these exact names
   - Change `recommendations` → `recommedations` (remove 'n')
   - Ensures consistency across entire system

2. **Option B:** Update orchestrator/kusto_client to match analyzer
   - Find/replace all instances
   - More work, but keeps analyzer unchanged

3. **Option C:** Create Kusto views
   ```kql
   .create function sparklens_recommendations() {
       sparklens_recommedations  // Note: backwards compatibility
   }
   ```

---

## 📝 **Column Name Mapping**

### **Key field name to use:**

```kql
-- For queries joining tables:
sparklens_metrics.application_id = sparklens_recommedations.app_id

-- Both refer to the same Spark application ID, just different column names
```

**Why different?**
- `sparklens_metrics` and `sparklens_metadata` likely come from Spark event logs → use standard `application_id`
- `sparklens_recommedations` and `fabric_recommedations` are generated by analyzer → use simpler `app_id`

---

## ✅ **Verification Commands**

Run these in your Kusto/Eventhouse to verify table existence:

```kql
// Check all tables exist
.show tables
| where TableName startswith "sparklens_" or TableName startswith "fabric_" or TableName == "sparkagent_feedback"

// Check schema matches
.show table sparklens_recommedations schema
.show table fabric_recommedations schema
.show table sparklens_metrics schema
.show table sparklens_metadata schema
.show table sparklens_predictions schema
.show table sparklens_summary schema
.show table sparkagent_feedback schema

// Sample data to verify column names
sparklens_recommedations | take 1
fabric_recommedations | take 1
sparklens_metrics | where metric == "Application Duration (sec)" | take 1
sparklens_metadata | take 1
```

---

## 🎯 **Summary**

✅ **All code is internally consistent**  
✅ **Table names match between orchestrator and kusto_client**  
⚠️ **Verify your analyzer writes to these exact table names**  
⚠️ **Note intentional misspelling: `recommedations` not `recommendations`**

**Next Step:** Share your analyzer code/notebook so I can verify it writes to matching table names.

---

**Generated:** 2026-02-22 by Fabric Spark Advisor Code Review
