# Diagnostic - App ID Mismatch Investigation

## Issue
User reports data EXISTS in `sparklens_recommedations` and `fabric_recommedations` tables,
but orchestrator returns "No recommendations found" when querying for specific application ID.

## Hypothesis
The app_id in the recommendations tables might be stored in a different format than what's being queried.

Possible mismatches:
1. **Underscore vs hyphen**: `application_1771443955490_0001` vs `application-1771443955490-0001`
2. **Case sensitivity**: `APPLICATION_1771443955490_0001` vs `application_1771443955490_0001`  
3. **Extra whitespace**: `application_1771443955490_0001 ` (trailing space)
4. **Column name mismatch**: Table uses `applicationId` instead of `app_id`

## Diagnostic Queries to Run

### 1. Check EXACT app_id format in sparklens_recommedations
```kql
sparklens_recommedations
| take 10
| project app_id, recommendation_preview = substring(recommendation, 0, 100)
```

### 2. Check if application exists in recommendations (case-insensitive)
```kql
sparklens_recommedations
| where tolower(app_id) contains "1771443955490"
| project app_id, recommendation_preview = substring(recommendation, 0, 100)
```

### 3. Count recommendations per app
```kql
sparklens_recommedations
| summarize rec_count = count() by app_id
| order by rec_count desc
| take 20
```

### 4. Check schema - what columns exist?
```kql
sparklens_recommedations
| getschema 
```

### 5. Cross-check metrics vs recommendations tables
```kql
let metrics_apps = sparklens_metrics
    | where metric == "Application Duration (sec)"
    | distinct app_id;
let rec_apps = sparklens_recommedations
    | distinct app_id;
metrics_apps
| join kind=leftanti rec_apps on app_id
| take 10
| project missing_recommendations_for_app_id = app_id
```

### 6. Exact match test for the specific app
```kql
sparklens_recommedations
| where app_id == "application_1771443955490_0001"
| project app_id, recommendation_preview = substring(recommendation, 0, 200)
```

## Expected vs Actual

**Expected:** Query #6 should return recommendations for `application_1771443955490_0001`  

**Actual:** If it returns empty, the issue is one of:
- App ID format mismatch (check Query #2 result)
- Wrong column name (check Query #4 schema)
- Data not actually written yet (check Query #3 counts)

## Fix Strategy

### If app_id format is different:
- Modify KustoClient queries to normalize app_id before filtering
- OR modify analyzer to write app_id in consistent format

### If column name is wrong:
- Update KustoClient queries to use correct column name

### If data doesn't exist:
- Re-run analyzer for these applications
- Check analyzer logs for write failures
