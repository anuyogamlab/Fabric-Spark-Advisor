# Authentication Setup for SparkAdvisor

## Issue
Your managed identity authentication is failing with permission errors. You need to set up service principal (client secret) authentication as a fallback.

## Quick Fix

Edit your `.env` file and replace the placeholder values with your actual Azure AD credentials:

```env
AZURE_TENANT_ID=your-tenant-id-here
AZURE_CLIENT_ID=your-client-id-here  
AZURE_CLIENT_SECRET=your-client-secret-here
```

## How to Get These Values

### Option 1: Use Existing App Registration (Recommended)

If you already have an app registration for this project:

1. **Find Tenant ID**:
   ```powershell
   az account show --query tenantId -o tsv
   ```

2. **Get from Azure Portal**:
   - Go to [Azure Portal](https://portal.azure.com)
   - Navigate to **Azure Active Directory** → **App registrations**
   - Find your app (or the one used for Fabric/Kusto access)
   - **Application (client) ID** = `AZURE_CLIENT_ID`
   - **Directory (tenant) ID** = `AZURE_TENANT_ID`
   - **Certificates & secrets** → Create new client secret = `AZURE_CLIENT_SECRET`

### Option 2: Create New App Registration

1. **Create App Registration**:
   ```powershell
   az ad app create --display-name "SparkAdvisor-MCP"
   ```

2. **Create Service Principal**:
   ```powershell
   az ad sp create --id <app-id-from-step-1>
   ```

3. **Create Client Secret**:
   ```powershell
   az ad app credential reset --id <app-id> --append
   ```
   This will output your `clientId`, `tenantId`, and `password` (client secret).

4. **Grant Kusto Access**:
   - Go to your Kusto database in Fabric
   - Grant the service principal **Database Viewer** role

## Verify Setup

After setting credentials, test the connection:

```powershell
python -c "from mcp_server.kusto_client import KustoClient; client = KustoClient(); print('✅ Connected!')"
```

## Alternative: Fix Managed Identity Permissions

If you prefer to use Managed Identity instead of client secret:

1. **Run PowerShell as Administrator**
2. **Grant access to token files**:
   ```powershell
   $tokenPath = "C:\ProgramData\AzureConnectedMachineAgent\Tokens"
   icacls $tokenPath /grant "${env:USERNAME}:(OI)(CI)F" /T
   ```

3. **Restart Azure Connected Machine Agent**:
   ```powershell
   Restart-Service himds
   ```

## Security Note

⚠️ **Never commit `.env` file to source control!**

Your `.gitignore` already excludes it, but double-check:
```bash
git status --ignored | grep .env
```
