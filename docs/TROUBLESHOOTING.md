# 🔧 Troubleshooting: "No Recommendations Found" Issue

## Problem
Getting "No Spark Advisor recommendations found" even though data exists in Kusto.

## Root Causes & Solutions

### 1. **Branding Prompts Not Updated** ✅ FIXED
**Issue:** `agent/prompts.py` was instructing AI to use "SparkLens" text  
**Fix Applied:** Updated all user-facing messages to "Spark Advisor"  
**Action Required:** Restart the Chainlit server for changes to take effect

```powershell
# Kill existing server and restart
Get-Process -Name python | Where-Object {$_.CommandLine -like "*chainlit*"} | Stop-Process -Force
cd "c:\Users\anuve\OneDrive - Microsoft\Documents\Spark Recommender MCP"
chainlit run ui/app.py
```

---

### 2. **Application ID Mismatch** ⚠️ CHECK THIS

**Possible Issues:**
- Typo in app_id when entered (e.g., extra space, wrong underscore)
- Kusto table uses different ID format than what you're querying
- App exists but with slightly different ID

**Diagnostic Steps:**

#### Option A: Using the Interactive Notebook

1. Open `notebooks/FabricSparkAdvisor_Interactive.ipynb`
2. Run cells 1-4 to initialize
3. Run cell 15 to list available app IDs:
   ```python
   list_available_apps(20)
   ```
4. Copy the EXACT app_id from the output
5. Run cell 14 to verify specific app:
   ```python
   check_app_in_kusto('application_1771446566369_0001')
   ```

#### Option B: Direct Kusto Query

Connect to your Eventhouse and run:

```kql
// Check if app exists
sparklens_recommedations 
| where app_id contains "1771446566369"
| distinct app_id
| take 10

// If found, check full record
sparklens_recommedations 
| where app_id == 'YOUR_EXACT_APP_ID_FROM_ABOVE'
| take 1
```

---

### 3. **Field Name Mismatch** ✅ VERIFIED FIXED

**Previous Issue:** Code was looking for `recommendations` (plural) instead of `recommendation` (singular)  
**Status:** Already fixed in:
- `agent/orchestrator.py` line 116, 138
- `mcp_server/kusto_client.py` line 142, 340

**Verification:**
```python
# In orchestrator.py - should be:
"text": row.get("recommendation", "")  # CORRECT ✅
# NOT:
"text": row.get("recommendations", "")  # WRONG ❌
```

---

### 4. **Server Not Restarted After Code Changes** ⚠️ COMMON ISSUE

**Symptoms:**
- Code updated but still seeing old messages
- "SparkLens" appears instead of "Spark Advisor"
- Changes don't take effect

**Solution:**
```powershell
# Force restart Chainlit
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *chainlit*"
cd "c:\Users\anuve\OneDrive - Microsoft\Documents\Spark Recommender MCP"
chainlit run ui/app.py --port 8000
```

---

### 5. **Kusto Connection Issues** ⚠️ CHECK CREDENTIALS

**Error Symptoms:**
- Empty results even though app exists
- Connection timeout
- Authentication failures

**Diagnostic:**
```powershell
# Test Kusto connection
cd "c:\Users\anuve\OneDrive - Microsoft\Documents\Spark Recommender MCP"
python -c "from mcp_server.kusto_client import KustoClient; client = KustoClient.from_env(); print('✅ Connected'); result = client.execute_query('sparklens_recommedations | count'); print(f'Total records: {result[0][\"Count\"]}')"
```

**Check `.env` file:**
```env
CLUSTER_URL=https://your-cluster.kusto.windows.net
DATABASE_NAME=your_database
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-secret
```

---

## Quick Verification Checklist

- [ ] **Restarted Chainlit server** after code changes
- [ ] **Verified exact app_id** exists in Kusto using diagnostic notebook
- [ ] **Confirmed Kusto connection** works with test query
- [ ] **Checked logs** for error messages during query
- [ ] **Tried different app_id** that definitely has data
- [ ] **Cleared browser cache** if using web UI

---

## Next Steps

1. **Restart the server:**
   ```powershell
   cd "c:\Users\anuve\OneDrive - Microsoft\Documents\Spark Recommender MCP"
   chainlit run ui/app.py
   ```

2. **Open the notebook** and run cell 15 to get valid app IDs:
   ```python
   list_available_apps(10)
   ```

3. **Test with a known-good app_id** from the list above

4. **If still not working**, run the Kusto connection test and share the output

---

## Expected vs Actual Output

### ✅ EXPECTED (after fixes):
```
Spark Advisor Recommendations
Source: Kusto — sparklens_recommedations | VERIFIED
✓ Found 3 recommendations for this application
[recommendation details...]
```

### ❌ BEFORE (old branding):
```
SparkLens Recommendations  ← OLD TEXT
No SparkLens recommendations found  ← OLD TEXT
```

---

**Last Updated:** 2025-02-22  
**Files Modified:**
- `agent/prompts.py` (branding)
- `agent/orchestrator.py` (field names - previously fixed)
- `ui/app.py` (UI text - previously fixed)
