# Azure Deployment Guide — Telemetry Graph Web App

> **Site:** `multigeograph.azurewebsites.net`
> **Runtime:** .NET 9 ASP.NET Core (`webapp/`)
> **Auth:** Azure Easy Auth (App Service Authentication)

## Cross-Tenant Setup

| Concept | Value |
|---------|-------|
| **Tenant A** (Resource tenant) | Hosts the App Service |
| **Tenant B** (Productivity tenant) | Microsoft tenant — users log in with `foo@microsoft.com` |
| **App Registration** | `f0d82b2b-5f1a-492a-8ab5-82976278168a` (single-tenant, in Tenant B) |

---

## 1. App Registration Updates

The existing app registration `f0d82b2b-5f1a-492a-8ab5-82976278168a` in **Tenant B** needs the following changes.

### Redirect URIs

**Production:**
```
https://multigeograph.azurewebsites.net/.auth/login/aad/callback
```

**Local development:**
```
https://localhost:5001/.auth/login/aad/callback
```

### Token Configuration

- Enable **ID tokens** (implicit grant)
- Enable **Access tokens** (implicit grant) — optional but useful for API calls

### az CLI Commands

Run these in **Tenant B** context:

```bash
# Add redirect URIs
az ad app update \
  --id f0d82b2b-5f1a-492a-8ab5-82976278168a \
  --web-redirect-uris \
    "https://multigeograph.azurewebsites.net/.auth/login/aad/callback" \
    "https://localhost:5001/.auth/login/aad/callback"

# Enable ID and access tokens
az ad app update \
  --id f0d82b2b-5f1a-492a-8ab5-82976278168a \
  --enable-id-token-issuance true \
  --enable-access-token-issuance true
```

### Portal Steps (Alternative)

1. Go to **Azure Portal** → **Microsoft Entra ID** (in Tenant B)
2. **App registrations** → find `f0d82b2b-5f1a-492a-8ab5-82976278168a`
3. **Authentication** blade:
   - Add platform → **Web**
   - Redirect URI: `https://multigeograph.azurewebsites.net/.auth/login/aad/callback`
   - Check **ID tokens** and **Access tokens** under Implicit grant
4. **Save**

---

## 2. App Service Creation (in Tenant A)

```bash
# Variables
RESOURCE_GROUP="rg-multigeograph"
APP_NAME="multigeograph"
LOCATION="westus2"
SKU="B1"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create App Service Plan
az appservice plan create \
  --name "${APP_NAME}-plan" \
  --resource-group $RESOURCE_GROUP \
  --sku $SKU \
  --is-linux false

# Create Web App (.NET 9)
az webapp create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --plan "${APP_NAME}-plan" \
  --runtime "dotnet:9"
```

---

## 3. Easy Auth Configuration

Configure App Service Authentication to use the **Tenant B** app registration.

### az CLI Commands

```bash
# The issuer URL must point to Tenant B
# Replace {TENANT_B_ID} with the actual Tenant B directory (tenant) ID
TENANT_B_ID="{your-tenant-b-directory-id}"
CLIENT_ID="f0d82b2b-5f1a-492a-8ab5-82976278168a"

# You'll also need a client secret from the app registration
# Create one in the Azure Portal under Certificates & secrets
CLIENT_SECRET="{your-client-secret}"

# Configure authentication (v2 auth settings)
az webapp auth config-version upgrade --name $APP_NAME --resource-group $RESOURCE_GROUP

az webapp auth microsoft update \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --client-id $CLIENT_ID \
  --client-secret $CLIENT_SECRET \
  --issuer "https://login.microsoftonline.com/$TENANT_B_ID/v2.0" \
  --allowed-audiences "api://$CLIENT_ID" \
  --yes

# Require authentication (no anonymous access)
az webapp auth update \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --enabled true \
  --action LoginWithAzureActiveDirectory \
  --token-store true
```

### Portal Steps (Alternative)

1. Go to **App Service** → `multigeograph` → **Authentication** blade
2. **Add identity provider** → **Microsoft**
3. App registration type: **"Provide the details of an existing app registration"**
4. Application (client) ID: `f0d82b2b-5f1a-492a-8ab5-82976278168a`
5. Client secret: *(create one in Tenant B app registration under Certificates & secrets)*
6. Issuer URL: `https://login.microsoftonline.com/{TENANT_B_ID}/v2.0`
7. Restrict access: **"Require authentication"**
8. Unauthenticated requests: **"HTTP 302 Found redirect: recommended for websites"**
9. Token store: **Enabled**

---

## 4. Deployment

### Manual Deployment

```powershell
# Build the app (from repo root)
.\build.ps1

# Deploy using zip deploy
cd publish
Compress-Archive -Path * -DestinationPath ..\deploy.zip -Force
cd ..

az webapp deploy `
  --name multigeograph `
  --resource-group rg-multigeograph `
  --src-path deploy.zip `
  --type zip
```

### GitHub Actions (CI/CD)

A workflow is provided at [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml).

**Setup:**
1. In the Azure Portal, go to **App Service** → `multigeograph` → **Deployment Center**
2. Download the **publish profile**
3. In your GitHub repo, go to **Settings** → **Secrets and variables** → **Actions**
4. Add a secret named `AZURE_WEBAPP_PUBLISH_PROFILE` with the publish profile XML content

Pushes to `main` will automatically build and deploy. You can also trigger manually via **workflow_dispatch**.

---

## 5. Verification

After deployment:

1. Browse to `https://multigeograph.azurewebsites.net`
2. You should be **redirected to Microsoft login** (Tenant B)
3. Log in with your `foo@microsoft.com` account
4. After auth, the graph visualization should load

---

## 6. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| **Login loop** | Redirect URI mismatch | Check that the redirect URI in the app registration exactly matches `https://multigeograph.azurewebsites.net/.auth/login/aad/callback` (no trailing slash difference) |
| **403 Forbidden** | Wrong tenant or issuer | Verify the app registration is in Tenant B and the issuer URL matches `https://login.microsoftonline.com/{TENANT_B_ID}/v2.0` |
| **CORS issues** | N/A | Not needed — the .NET app serves both the frontend and API from the same origin |
| **Graph data missing** | Data not in publish output | Ensure `data/sample/` or `data/graph/` was included in the publish output |
| **500 on startup** | Runtime mismatch | Confirm the App Service is configured for .NET 9 (`dotnet:9`) |
| **Auth token missing in headers** | Token store disabled | Enable the token store in Easy Auth settings |
