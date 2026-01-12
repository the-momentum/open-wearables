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

### Key Files to Create

For a new provider (e.g., "strava"):

```
backend/app/services/providers/strava/
├── __init__.py
├── strategy.py           # StravaStrategy(BaseProviderStrategy)
├── oauth.py              # StravaOAuth(BaseOAuthTemplate)
├── workouts.py           # StravaWorkouts(BaseWorkoutsTemplate)
└── data_247.py           # Optional: Strava247Data(Base247DataTemplate)
```

Additional files:
```
backend/app/constants/workout_types/strava.py   # Workout type mappings
backend/app/static/provider-icons/strava.svg    # Provider icon
```

Files to modify:
```
backend/app/services/providers/factory.py       # Register in ProviderFactory
backend/app/schemas/oauth.py                    # Add to ProviderName enum
backend/app/config.py                           # Add OAuth credentials
```

### Existing Providers for Reference

| Provider | OAuth | Workouts | 247 Data | Pattern |
|----------|-------|----------|----------|---------|
| Garmin | Yes (PKCE) | Yes | No | PULL + PUSH |
| Polar | Yes | Yes | No | PULL |
| Suunto | Yes | Yes | Yes | PULL |
| Whoop | Yes | No | Yes | PULL |
| Apple | No | Yes | No | PUSH only |

Study existing implementations in `backend/app/services/providers/` before starting.

## Getting Started

1. Read the [comprehensive guide](../docs/dev-guides/how-to-add-new-provider.mdx)
2. Study existing providers in `backend/app/services/providers/`
3. Open an issue to discuss your integration approach
4. Submit a PR with your implementation
