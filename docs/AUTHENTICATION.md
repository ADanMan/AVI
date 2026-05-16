# Authentication & Authorization

## Overview

AVI uses API Key-based authentication with Role-Based Access Control (RBAC) for securing endpoints.

## Features

- **API Key Authentication**: X-API-Key header for all authenticated requests
- **Role-Based Access Control**: Three role levels (admin, user, readonly)
- **Secure Storage**: Keys stored as SHA-256 hashes
- **Expiration Support**: Optional key expiration
- **Last Used Tracking**: Audit trail for key usage

## Roles

### Admin
- Full access to all endpoints
- Can manage API keys (create, revoke, delete)
- Can perform system administration tasks
- Inherits all user and readonly permissions

### User
- Can query the LLM (POST /api/v1/query, POST /api/v1/chat/*)
- Can filter content and manage safety settings
- Can upload documents and rules (POST /api/v1/upload/*)
- Can manage documents and rules (POST/PATCH/DELETE /api/v1/rules/*)
- Can modify system configuration (POST /api/v1/settings/*)
- Can run experiments (POST /api/v1/experiments/*)
- Inherits all readonly permissions

### Readonly
- Can view statistics (GET /api/v1/stats)
- Can check system health (GET /api/v1/health)
- Can list documents and rules (GET /api/v1/rules)
- Can view monitoring data (GET /api/v1/monitoring/*)
- Can check filter configuration (GET /api/v1/filters/*)
- Cannot modify any data

## Quick Start

### 1. Bootstrap First Admin Key

```bash
# Create the first admin API key
python scripts/bootstrap_admin_key.py --name "Production Admin"

# Save the displayed API key securely!
```

**Important**: The plaintext API key is shown **only once**. Save it immediately!

### 2. Configure Environment

```bash
# For clients/UI/CLI that call the API
export AVI_API_KEY=avi_<your-key-here>

# For production: require authentication
export REQUIRE_API_KEY=true
```

### 3. Use the API

```bash
# Make authenticated requests
curl -H "X-API-Key: avi_<your-key>" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is AI?"}' \
  http://localhost:8000/query
```

## Managing API Keys

### CLI Tool

```bash
# List all API keys
python scripts/manage_api_keys.py list

# Create a new user key
python scripts/manage_api_keys.py create \
  --name "App Key" \
  --role user \
  --expires-days 90

# Revoke a key
python scripts/manage_api_keys.py revoke <key_hash>

# Delete a key permanently
python scripts/manage_api_keys.py delete <key_hash>
```

### API Endpoints

All key management endpoints require **admin** role:

```bash
# Create new API key
curl -X POST http://localhost:8000/admin/keys \
  -H "X-API-Key: <admin-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My App",
    "role": "user",
    "expires_days": 90
  }'

# List all keys
curl -H "X-API-Key: <admin-key>" \
  http://localhost:8000/admin/keys

# Revoke a key
curl -X POST http://localhost:8000/admin/keys/revoke \
  -H "X-API-Key: <admin-key>" \
  -H "Content-Type: application/json" \
  -d '{"key_hash": "<full-hash>"}'

# Delete a key
curl -X DELETE http://localhost:8000/admin/keys \
  -H "X-API-Key: <admin-key>" \
  -H "Content-Type: application/json" \
  -d '{"key_hash": "<full-hash>"}'
```

## Configuration

### Settings

```bash
# Authentication
REQUIRE_API_KEY=false  # Set to true in production
API_KEY_HEADER=X-API-Key  # Header name for API keys

# Client configuration (for UI/CLI)
AVI_API_KEY=<your-api-key>  # Key for internal API calls
AVI_API_BASE=http://localhost:8000  # API base URL
```

### Optional vs Required Authentication

By default, authentication is **optional** (`REQUIRE_API_KEY=false`):
- All endpoints work without authentication (development mode)
- Useful for testing and local development
- Admin endpoints still require authentication and admin role

In production, set `REQUIRE_API_KEY=true`:
- **All API endpoints** require valid API key with appropriate role
- Requests without API key will receive 401 Unauthorized
- Admin endpoints require admin role
- Recommended for production deployments

### Protected Endpoints

**ALL API endpoints are now protected** with role-based access control:

#### USER Role Required:
- `POST /api/v1/query` - Process queries
- `POST /api/v1/query/stream` - Streaming queries
- `POST /api/v1/chat/*` - Chat endpoints
- `POST /api/v1/upload/*` - Upload documents/rules
- `POST /api/v1/cache/clear` - Clear cache
- `POST /api/v1/reindex` - Reindex data
- `POST/PATCH/DELETE /api/v1/rules/*` - Manage rules
- `POST /api/v1/settings/*` - Update settings
- `POST /api/v1/experiments/*` - Run experiments

#### READONLY Role Required:
- `GET /api/v1/health` - System health
- `GET /api/v1/stats` - System statistics
- `GET /api/v1/rules` - List rules
- `GET /api/v1/monitoring/*` - Monitoring data
- `GET /api/v1/filters/*` - Filter configuration
- `GET /api/v1/settings/*` - View settings
- `GET /api/v1/indexing/status` - Indexing status

#### ADMIN Role Required:
- `POST /api/v1/admin/keys` - Create API keys
- `GET /api/v1/admin/keys` - List API keys
- `POST /api/v1/admin/keys/revoke` - Revoke keys
- `DELETE /api/v1/admin/keys` - Delete keys

## Storage

API keys are stored in:
```
data/security/api_keys.json
```

**Important**:
- Keys are stored as SHA-256 hashes
- Plaintext keys are NEVER stored
- Back up this file securely
- Add to `.gitignore` to prevent committing

## Security Best Practices

### For Administrators

1. **Use strong, unique keys**: Generated keys are 32-byte URL-safe tokens
2. **Set expiration dates**: Use `--expires-days` for temporary keys
3. **Regular key rotation**: Revoke old keys, create new ones periodically
4. **Monitor last used**: Check key usage via list command
5. **Enable required auth in production**: Set `REQUIRE_API_KEY=true`
6. **Backup key storage**: Secure the `api_keys.json` file

### For Developers

1. **Never commit API keys**: Keep keys in environment variables or `.env` files
2. **Use environment-specific keys**: Different keys for dev/staging/prod
3. **Request minimum required role**: Use `readonly` for read-only operations
4. **Handle 401/403 errors**: Implement proper error handling
5. **Rotate keys regularly**: Update keys in your applications periodically

## Troubleshooting

### "Invalid API key" Error

1. Check the key is correct (copy-paste carefully)
2. Verify the key hasn't been revoked or expired
3. Ensure you're using the correct header: `X-API-Key`
4. Check the key exists: `python scripts/manage_api_keys.py list`

### "Insufficient permissions" Error

1. Check your key's role: `python scripts/manage_api_keys.py list -v`
2. Verify the endpoint requires your role or lower
3. For admin operations, ensure you have admin role

### "API key required" Error

1. `REQUIRE_API_KEY=true` is set (production mode)
2. Add X-API-Key header to all requests
3. Or set `REQUIRE_API_KEY=false` for development

## Migration Guide

### From No Authentication

1. Create admin key: `python scripts/bootstrap_admin_key.py`
2. Update API client code to include X-API-Key header
3. Test with `REQUIRE_API_KEY=false`
4. Enable in production: `REQUIRE_API_KEY=true`

### From Bearer Token

1. Replace `Authorization: Bearer <token>` with `X-API-Key: <key>`
2. Update client code to use new header
3. Create API keys for all users/apps
4. Retire old token system

## Examples

### Python Client

```python
import httpx
from config.settings import settings

# Initialize client
headers = {settings.API_KEY_HEADER: settings.AVI_API_KEY}

# Make request
async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{settings.AVI_API_BASE}/query",
        json={"query": "What is AI?"},
        headers=headers
    )
    print(response.json())
```

### JavaScript Client

```javascript
// Make authenticated request
fetch('http://localhost:8000/query', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': process.env.AVI_API_KEY
  },
  body: JSON.stringify({ query: 'What is AI?' })
})
.then(response => response.json())
.then(data => console.log(data));
```

### cURL Examples

```bash
# Query endpoint
curl -X POST http://localhost:8000/query \
  -H "X-API-Key: $AVI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is AI?"}'

# Get stats
curl -H "X-API-Key: $AVI_API_KEY" \
  http://localhost:8000/stats

# Create new API key (admin only)
curl -X POST http://localhost:8000/admin/keys \
  -H "X-API-Key: $AVI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "New Key", "role": "user"}'
```

## FAQ

**Q: Where is the plaintext API key stored?**
A: Nowhere! Plaintext keys are shown only once at creation and never stored.

**Q: Can I retrieve a lost API key?**
A: No. You must revoke the old key and create a new one.

**Q: How do I rotate API keys?**
A: Create a new key, update your applications, then revoke the old key.

**Q: Can I have multiple admin keys?**
A: Yes. You can create as many admin keys as needed.

**Q: What happens if all admin keys are lost?**
A: Run `scripts/bootstrap_admin_key.py` again to create a new admin key.

**Q: Are API keys rate-limited separately?**
A: Yes. Rate limiting is applied per API key hash.

**Q: Can I use the same key for multiple applications?**
A: Technically yes, but create separate keys for better tracking and security.
