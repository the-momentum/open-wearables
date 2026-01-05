# Adding a New Provider

This guide covers how to add support for a new wearable device provider to Open Wearables.

## Overview

Open Wearables uses a provider strategy pattern to support multiple wearable device integrations. Each provider implements OAuth authentication and data fetching for their specific API.

## Comprehensive Guide

For detailed, step-by-step instructions on adding a new provider, see the comprehensive guide:

**[How to Add a New Provider](../docs/dev-guides/how-to-add-new-provider.mdx)**

This guide covers:

- Creating provider configuration
- Implementing OAuth flow
- Building data transformers
- Adding API routes
- Database migrations
- Testing your integration
- Frontend integration

## Quick Reference

### Key Files to Create/Modify

```
backend/
├── app/
│   ├── services/providers/
│   │   └── your_provider.py      # Provider implementation
│   ├── api/routes/v1/
│   │   └── your_provider.py      # API routes
│   └── constants/
│       └── providers.py          # Add provider enum
```

### Provider Implementation Pattern

```python
from app.services.providers.base import BaseProvider

class YourProvider(BaseProvider):
    name = "your_provider"

    async def get_authorization_url(self) -> str:
        # Generate OAuth URL
        pass

    async def exchange_code(self, code: str) -> TokenData:
        # Exchange auth code for tokens
        pass

    async def fetch_data(self, user_id: int) -> ProviderData:
        # Fetch user health data
        pass
```

## Getting Started

1. Read the [comprehensive guide](../docs/dev-guides/how-to-add-new-provider.mdx)
2. Study existing providers in `backend/app/services/providers/`
3. Open an issue to discuss your integration approach
4. Submit a PR with your implementation
