# Ultrahuman Provider - ngrok Setup Guide

## Overview
This document summarizes the ngrok setup for the Ultrahuman Ring Air provider integration. Ultrahuman requires HTTPS redirect URLs (HTTP is not allowed), so ngrok is used to create a secure tunnel for local development.

## What Was Done

### 1. Fixed Ultrahuman Redirect URI Configuration
**Files Modified:**
- `backend/app/config.py` - Changed default from `http://localhost:8000` to `https://your-domain.com`
- `backend/config/.env.example` - Updated with HTTPS and documentation about the requirement

### 2. Installed ngrok
- **Version**: 3.35.0
- **Installation Method**: AUR (Arch Linux)
- **Command Used**: `yay -S ngrok`

### 3. Configured ngrok Authentication
- **Action**: Added authtoken via `ngrok config add-authtoken <token>`
- **Required**: Free ngrok account from https://dashboard.ngrok.com/signup

### 4. Started ngrok Tunnel
- **Command**: `ngrok http 8000`
- **Local Endpoint**: `http://localhost:8000`
- **Public HTTPS URL**: `https://vitascopic-rosita-squabbiest.ngrok-free.dev`

### 5. Updated Environment Configuration
**File**: `backend/config/.env`

```bash
#--- Ultrahuman ---#
# Note: Ultrahuman requires HTTPS redirect URLs (ngrok tunnel)
ULTRAHUMAN_CLIENT_ID=your-ultrahuman-client-id
ULTRAHUMAN_CLIENT_SECRET=your-ultrahuman-client-secret
ULTRAHUMAN_REDIRECT_URI=https://vitascopic-rosita-squabbiest.ngrok-free.dev/api/v1/oauth/ultrahuman/callback
ULTRAHUMAN_DEFAULT_SCOPE=ring_data cgm_data profile
```

## Current ngrok Tunnel

| Property | Value |
|----------|-------|
| **Public URL** | `https://vitascopic-rosita-squabbiest.ngrok-free.dev` |
| **Local Target** | `http://localhost:8000` |
| **Status** | Running |
| **Process IDs** | 60722, 60725, 61553 |
| **Log File** | `/tmp/ngrok/ngrok.log` |

## Next Steps

### Step 1: Register App in Ultrahuman Portal

1. Go to the [Ultrahuman Partnership API](https://vision.ultrahuman.com/developer-docs)
2. Create a new app/application
3. Set the **Redirect URI** to:
   ```
   https://vitascopic-rosita-squabbiest.ngrok-free.dev/api/v1/oauth/ultrahuman/callback
   ```
4. Note your **Client ID** and **Client Secret**

### Step 2: Add Ultrahuman Credentials to `.env`

Update `backend/config/.env` with your actual credentials:

```bash
ULTRAHUMAN_CLIENT_ID=<your-actual-client-id>
ULTRAHUMAN_CLIENT_SECRET=<your-actual-client-secret>
```

### Step 3: Start the Backend Server

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Or using Docker:
```bash
docker compose up -d
```

### Step 4: Test OAuth Flow

1. Open the developer portal: `http://localhost:3000`
2. Navigate to Connections
3. Click "Connect" next to Ultrahuman
4. Complete the OAuth flow in the Ultrahuman portal
5. Verify the connection is saved

### Step 5: Verify Data Sync

Once connected, verify that data sync works:
```bash
# Check for Ultrahuman data in the database
# Or view through the developer portal UI
```

## Important Notes

### ngrok URL Changes
- The ngrok tunnel URL (`vitascopic-rosita-squabbiest.ngrok-free.dev`) changes each time ngrok restarts
- If ngrok stops, you must:
  1. Restart ngrok: `ngrok http 8000`
  2. Get the new URL from the output or API: `curl -s http://127.0.0.1:4040/api/tunnels`
  3. Update `ULTRAHUMAN_REDIRECT_URI` in `.env`
  4. Re-register the app in Ultrahuman portal (or update if supported)

### ngrok Commands

```bash
# Start ngrok tunnel
ngrok http 8000

# Get current tunnel URL via API
curl -s http://127.0.0.1:4040/api/tunnels | grep -o "https://[^\"]*"

# Check ngrok version
ngrok version

# View ngrok configuration
ngrok config check

# Stop ngrok
pkill -f "ngrok http"
```

### Production Deployment

For production, replace the ngrok URL with your actual domain's HTTPS URL:

```bash
ULTRAHUMAN_REDIRECT_URI=https://your-actual-domain.com/api/v1/oauth/ultrahuman/callback
```

## Troubleshooting

### ngrok authentication failed
**Error**: `ERR_NGROK_4018`

**Solution**: Add your authtoken
```bash
ngrok config add-authtoken <your-token>
```

### Ultrahuman portal rejects redirect URL
**Error**: "Invalid redirect URI" or similar

**Solution**: Ensure the URL uses HTTPS (not HTTP) and matches exactly what's in your `.env` file.

### OAuth callback fails
**Error**: Connection refused or timeout

**Solution**: Ensure ngrok is running and the backend server is started on port 8000.

## Resources

- **ngrok Dashboard**: https://dashboard.ngrok.com/
- **ngrok Docs**: https://ngrok.com/docs
- **Ultrahuman API Docs**: https://vision.ultrahuman.com/developer-docs
- **Ultrahuman Blog**: https://blog.ultrahuman.com/blog/accessing-the-ultrahuman-partnership-api/

## Ultrahuman API Endpoints

- **Authorization**: https://auth.ultrahuman.com/authorize
- **Token Exchange**: https://partner.ultrahuman.com/api/partners/oauth/token
- **API Base**: https://partner.ultrahuman.com/api/partners/v1
- **User Info**: /user_data/user_info
- **Metrics**: /user_data/metrics
- **Sleep**: /user_data/sleep (candidate - needs verification)
- **Recovery**: /user_data/recovery (candidate - needs verification)

## Implementation Summary

The Ultrahuman Ring Air provider has been fully implemented with the following components:

### Files Created
- `backend/app/services/providers/ultrahuman/strategy.py` - Provider strategy
- `backend/app/services/providers/ultrahuman/oauth.py` - OAuth 2.0 implementation
- `backend/app/services/providers/ultrahuman/data_247.py` - Sleep, recovery, and activity data handler
- `backend/app/static/provider-icons/ultrahuman.svg` - Provider icon

### Tests Created
- `backend/tests/providers/ultrahuman/test_ultrahuman_oauth.py`
- `backend/tests/providers/ultrahuman/test_ultrahuman_strategy.py`
- `backend/tests/providers/ultrahuman/test_ultrahuman_data_247.py`

### Factory Registration
- `backend/app/services/providers/factory.py` - Ultrahuman registered
- `backend/app/schemas/oauth.py` - `ULTRAHUMAN` added to `ProviderName` enum

### Configuration
- `backend/app/config.py` - OAuth settings added
- `backend/config/.env.example` - Environment variables documented
- `backend/config/.env` - Local environment configured with ngrok URL

---

**Last Updated**: 2025-01-14
