# Azure Portal Setup Guide for Microsoft Graph API

This guide walks you through setting up Azure Active Directory (Entra ID) and generating the credentials required to access Microsoft Graph API for email operations.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Create an Azure Account](#create-an-azure-account)
3. [Register an Application in Azure AD](#register-an-application-in-azure-ad)
4. [Configure API Permissions](#configure-api-permissions)
5. [Create Client Credentials](#create-client-credentials)
6. [Grant Admin Consent](#grant-admin-consent)
7. [Configure Authentication Settings](#configure-authentication-settings)
8. [Retrieve Your Credentials](#retrieve-your-credentials)
9. [Environment Variables Setup](#environment-variables-setup)
10. [Testing Your Setup](#testing-your-setup)
11. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have:

- A Microsoft 365 account (work or school) or a Microsoft account
- Admin access to Azure Active Directory (for granting admin consent)
- Access to mailboxes you want to read/send emails from

---

## Create an Azure Account

If you don't have an Azure account:

1. Go to [Azure Portal](https://portal.azure.com)
2. Click **Start free** or **Sign in**
3. Follow the registration process
4. Complete identity verification

> **Note**: Microsoft 365 Developer Program offers a free sandbox environment for testing: [Join the Developer Program](https://developer.microsoft.com/en-us/microsoft-365/dev-program)

---

## Register an Application in Azure AD

### Step 1: Navigate to App Registrations

1. Sign in to the [Azure Portal](https://portal.azure.com)
2. In the search bar, type **"App registrations"** and select it
3. Alternatively, navigate to: **Azure Active Directory** → **App registrations**

### Step 2: Create a New Registration

1. Click **+ New registration**

2. Fill in the application details:

   | Field | Value | Description |
   |-------|-------|-------------|
   | **Name** | `email-automation-app` | Display name for your app |
   | **Supported account types** | Select based on your needs (see below) | Who can use this app |
   | **Redirect URI** | Leave blank for now (or set if using delegated flow) | For OAuth callbacks |

3. **Supported Account Types Options**:
   - **Single tenant**: Only accounts in your organization
   - **Multitenant**: Accounts in any Azure AD organization
   - **Multitenant + personal**: Azure AD + personal Microsoft accounts

4. Click **Register**

### Step 3: Note Your Application IDs

After registration, you'll see the **Overview** page. Record these values:

| Value | Description | Example |
|-------|-------------|---------|
| **Application (client) ID** | Unique identifier for your app | `12345678-1234-1234-1234-123456789abc` |
| **Directory (tenant) ID** | Your Azure AD tenant identifier | `87654321-4321-4321-4321-cba987654321` |

---

## Configure API Permissions

### Step 1: Navigate to API Permissions

1. In your app registration, click **API permissions** in the left sidebar
2. Click **+ Add a permission**
3. Select **Microsoft Graph**

### Step 2: Choose Permission Type

You have two options:

#### Option A: Delegated Permissions (User Context)

Used when the app acts on behalf of a signed-in user.

1. Select **Delegated permissions**
2. Add these permissions for email operations:

| Permission | Description | Admin Consent Required |
|------------|-------------|------------------------|
| `Mail.Read` | Read user's mail | No |
| `Mail.ReadWrite` | Read and write user's mail | No |
| `Mail.Send` | Send mail as the user | No |
| `Mail.ReadBasic` | Read basic mail properties | No |
| `User.Read` | Sign in and read user profile | No |

#### Option B: Application Permissions (Daemon/Service)

Used for background services without user interaction.

1. Select **Application permissions**
2. Add these permissions:

| Permission | Description | Admin Consent Required |
|------------|-------------|------------------------|
| `Mail.Read` | Read mail in all mailboxes | **Yes** |
| `Mail.ReadWrite` | Read and write mail in all mailboxes | **Yes** |
| `Mail.Send` | Send mail as any user | **Yes** |

### Step 3: Add Permissions

1. Check the boxes for the permissions you need
2. Click **Add permissions**

### Recommended Permissions for This Project

For the email automation system, use **Application permissions**:

```
Mail.Read
Mail.ReadWrite  
Mail.Send
```

---

## Create Client Credentials

### Option A: Client Secret (Recommended for Development)

1. In your app registration, click **Certificates & secrets**
2. Under **Client secrets**, click **+ New client secret**
3. Configure the secret:

   | Field | Recommendation |
   |-------|----------------|
   | **Description** | `email-automation-secret` |
   | **Expires** | 24 months (or as per your security policy) |

4. Click **Add**
5. **IMPORTANT**: Copy the secret **Value** immediately (it won't be shown again)

   | Field | What to Copy |
   |-------|--------------|
   | **Value** | The actual secret (e.g., `abc123~XyZ...`) — **Use this** |
   | **Secret ID** | UUID of the secret — Not needed for auth |

### Option B: Certificate (Recommended for Production)

1. Generate a self-signed certificate or obtain one from a CA:

   ```powershell
   # PowerShell - Generate self-signed certificate
   $cert = New-SelfSignedCertificate -Subject "CN=email-automation-app" `
       -CertStoreLocation "Cert:\CurrentUser\My" `
       -KeyExportPolicy Exportable `
       -KeySpec Signature `
       -KeyLength 2048 `
       -KeyAlgorithm RSA `
       -HashAlgorithm SHA256 `
       -NotAfter (Get-Date).AddYears(2)
   
   # Export the public key (.cer) for Azure
   Export-Certificate -Cert $cert -FilePath "email-automation-app.cer"
   
   # Export the private key (.pfx) for your application
   $pwd = ConvertTo-SecureString -String "YourPassword" -Force -AsPlainText
   Export-PfxCertificate -Cert $cert -FilePath "email-automation-app.pfx" -Password $pwd
   ```

2. Upload the certificate (.cer file) to Azure:
   - Go to **Certificates & secrets** → **Certificates**
   - Click **Upload certificate**
   - Select your `.cer` file and click **Add**

---

## Grant Admin Consent

Application permissions require admin consent.

### If You Are an Admin

1. Go to **API permissions** in your app registration
2. Click **Grant admin consent for [Your Organization]**
3. Confirm by clicking **Yes**
4. All permissions should now show a green checkmark under "Status"

### If You Are Not an Admin

1. Click **Grant admin consent** — this will show a request form
2. Or ask your Azure AD admin to:
   - Navigate to **Enterprise applications** → Your app → **Permissions**
   - Click **Grant admin consent**

### Verify Consent Status

| Status | Meaning |
|--------|---------|
| ✅ Green checkmark | Consent granted |
| ⚠️ "Not granted" | Consent pending |

---

## Configure Authentication Settings

### For Application (Daemon) Flow

No additional redirect URIs needed for client credentials flow.

### For Delegated (User) Flow

1. Go to **Authentication** in your app registration
2. Click **+ Add a platform**
3. Choose your platform:

#### Web Application

```
Redirect URI: https://localhost:8000/callback
              https://your-domain.com/auth/callback
```

#### Mobile/Desktop Application

```
Redirect URI: https://login.microsoftonline.com/common/oauth2/nativeclient
              http://localhost
```

4. Configure additional settings:

   | Setting | Value |
   |---------|-------|
   | **Access tokens** | ✅ Check (for implicit flow) |
   | **ID tokens** | ✅ Check (for OpenID Connect) |

5. Click **Configure**

---

## Retrieve Your Credentials

### Summary of Required Values

Navigate to your app registration and collect:

| Credential | Location | Example |
|------------|----------|---------|
| **Tenant ID** | Overview page | `87654321-4321-4321-4321-cba987654321` |
| **Client ID** | Overview page | `12345678-1234-1234-1234-123456789abc` |
| **Client Secret** | Certificates & secrets | `abc123~XyZsecretvalue...` |

### Find Your Values

1. **Tenant ID and Client ID**: App registration → Overview
2. **Client Secret**: App registration → Certificates & secrets (create new if needed)

---

## Environment Variables Setup

Create or update your `.env` file with the Azure credentials:

```env
# Azure AD / Microsoft Graph API Credentials
AZURE_TENANT_ID=87654321-4321-4321-4321-cba987654321
AZURE_CLIENT_ID=12345678-1234-1234-1234-123456789abc
AZURE_CLIENT_SECRET=abc123~XyZsecretvalue...

# Optional: Specify the mailbox to access (for application permissions)
GRAPH_USER_ID=trade@company.com

# Existing credentials
OPENAI_API_KEY=sk-...
```

### Security Best Practices

1. **Never commit `.env` to version control**
   ```gitignore
   # .gitignore
   .env
   *.pem
   *.pfx
   *.cer
   ```

2. **Use Azure Key Vault in production** for secure credential storage

3. **Rotate secrets regularly** — set calendar reminders before expiration

4. **Use certificates** instead of secrets for production workloads

---

## Testing Your Setup

### Quick Test with Azure CLI

```bash
# Install Azure CLI if needed
# https://docs.microsoft.com/en-us/cli/azure/install-azure-cli

# Login
az login

# Get an access token for Graph API
az account get-access-token --resource https://graph.microsoft.com
```

### Test with Python

```python
"""Quick test to verify Azure credentials."""

import os
from azure.identity import ClientSecretCredential

# Load from environment
tenant_id = os.getenv("AZURE_TENANT_ID")
client_id = os.getenv("AZURE_CLIENT_ID")
client_secret = os.getenv("AZURE_CLIENT_SECRET")

# Create credential
credential = ClientSecretCredential(
    tenant_id=tenant_id,
    client_id=client_id,
    client_secret=client_secret,
)

# Get token
token = credential.get_token("https://graph.microsoft.com/.default")
print(f"Token acquired successfully!")
print(f"Token expires at: {token.expires_on}")
```

### Test API Access

```python
import requests

# Use the token from above
headers = {"Authorization": f"Bearer {token.token}"}

# Test: Get user info (requires User.Read)
response = requests.get(
    "https://graph.microsoft.com/v1.0/me",
    headers=headers
)
print(response.json())
```

---

## Troubleshooting

### Common Errors

#### Error: `AADSTS7000215: Invalid client secret`

**Cause**: Client secret is incorrect or expired.

**Solution**:
1. Go to **Certificates & secrets**
2. Check if secret has expired
3. Create a new secret and update `.env`

#### Error: `AADSTS700016: Application not found in tenant`

**Cause**: Wrong tenant ID or app not registered in this tenant.

**Solution**:
1. Verify you're in the correct Azure AD tenant
2. Check the **Directory (tenant) ID** matches your `.env`

#### Error: `AADSTS65001: User or admin has not consented`

**Cause**: Admin consent not granted for application permissions.

**Solution**:
1. Go to **API permissions**
2. Click **Grant admin consent**
3. Ensure all permissions show green checkmarks

#### Error: `Authorization_RequestDenied`

**Cause**: Missing required permissions.

**Solution**:
1. Verify the required permissions are added
2. Ensure admin consent is granted
3. Check the specific permission needed for your API call

#### Error: `InvalidAuthenticationToken`

**Cause**: Token is expired, malformed, or for wrong audience.

**Solution**:
1. Request a new token
2. Verify the resource/scope is `https://graph.microsoft.com/.default`
3. Check token hasn't expired

### Useful Diagnostic Tools

1. **Microsoft Graph Explorer**: [https://developer.microsoft.com/graph/graph-explorer](https://developer.microsoft.com/graph/graph-explorer)
   - Test API calls interactively
   - See required permissions for each endpoint

2. **JWT Decoder**: [https://jwt.ms](https://jwt.ms)
   - Decode your access tokens
   - Verify claims, audience, and expiration

3. **Azure AD Sign-in Logs**:
   - Azure Portal → Azure Active Directory → Sign-in logs
   - Filter by your application

---

## Next Steps

Once your Azure setup is complete:

1. Proceed to **[Graph API Integration Guide](./GRAPH_API_INTEGRATION_GUIDE.md)** for Python implementation
2. Replace the mock `GraphMockProvider` with the real `GraphProvider`
3. Test with your actual mailbox

---

## Quick Reference

### API Endpoints

| Operation | Endpoint | Permission |
|-----------|----------|------------|
| List messages | `GET /users/{id}/messages` | Mail.Read |
| Get message | `GET /users/{id}/messages/{id}` | Mail.Read |
| Send mail | `POST /users/{id}/sendMail` | Mail.Send |
| Create draft | `POST /users/{id}/messages` | Mail.ReadWrite |
| Reply to message | `POST /users/{id}/messages/{id}/reply` | Mail.Send |

### Token Endpoints

| Flow | Endpoint |
|------|----------|
| Token (v2.0) | `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token` |
| Authorize (v2.0) | `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize` |

### Scopes

| Scope | Description |
|-------|-------------|
| `https://graph.microsoft.com/.default` | All statically configured permissions |
| `https://graph.microsoft.com/Mail.Read` | Specific delegated permission |
