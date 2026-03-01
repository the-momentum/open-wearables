# Ultrahuman Testing Agent

This document describes the Ultrahuman integration testing agent, its components, and how to use them.

## Overview

The Ultrahuman testing agent provides comprehensive test coverage for the Ultrahuman Ring Air integration with Open Wearables. It focuses on end-to-end API tests with real API calls (not mocked responses) and automated verification of data integrity.

## Components

### 1. Integration Tests

**File:** `backend/tests/providers/ultrahuman/test_ultrahuman_integration.py`

End-to-end integration tests that verify the complete data flow from Ultrahuman API to database storage.

#### Test Classes

- **`TestUltrahumanSleepDataIntegration`** - Sleep data sync and storage verification
  - `test_full_sleep_sync_flow()` - Complete sync flow
  - `test_verify_sleep_records_in_database()` - Database record validation
  - `test_sleep_efficiency_extraction()` - Efficiency score validation
  - `test_sleep_stage_values_are_nonzero()` - Sleep stage parsing verification

- **`TestUltrahumanActivitySamplesIntegration`** - Activity samples sync and storage verification
  - `test_full_activity_samples_sync_flow()` - Complete sync flow
  - `test_verify_activity_samples_in_database()` - Database sample validation
  - `test_heart_rate_values_are_reasonable()` - HR range validation (40-200 bpm)
  - `test_temperature_values_are_reasonable()` - Temperature range validation (35-42°C)
  - `test_timestamps_are_utc()` - Timezone verification

- **`TestUltrahumanAPIEndpoints`** - API endpoint tests
  - `test_sleep_events_endpoint_returns_data()` - Sleep events endpoint validation
  - `test_timeseries_endpoint_returns_data()` - Timeseries endpoint validation

- **`TestUltrahumanErrorHandling`** - Error scenario tests
  - `test_sync_handles_no_data_days()` - Empty date handling
  - `test_sync_handles_partial_data()` - Partial data handling
  - `test_sync_respects_date_range()` - Date boundary validation

### 2. Unit Tests

**File:** `backend/tests/providers/ultrahuman/test_ultrahuman_data_247.py`

Unit tests for data normalization and processing logic.

#### Test Classes

- **`TestUltrahuman247Data`** - Basic initialization tests
  - `test_ultrahuman_247_initialization()` - Provider setup verification

- **`TestUltrahumanSleepData`** - Sleep data normalization tests
  - `test_normalize_sleep_with_complete_data()` - Full data handling
  - `test_normalize_sleep_with_minimal_data()` - Minimal data handling

- **`TestUltrahumanRecoveryData`** - Recovery data normalization tests
  - `test_normalize_recovery_with_complete_data()` - Full data handling

- **`TestUltrahumanActivitySamples`** - Activity samples normalization tests
  - `test_normalize_activity_samples()` - Sample processing verification

### 3. OAuth Tests

**File:** `backend/tests/providers/ultrahuman/test_ultrahuman_oauth.py`

OAuth flow and authentication tests.

#### Test Classes

- **`TestUltrahumanOAuthConfiguration`** - OAuth endpoint and credential configuration
- **`TestUltrahumanOAuthAuthorization`** - Authorization URL generation
- **`TestUltrahumanOAuthUserInfo`** - User profile data extraction

### 4. Strategy Tests

**File:** `backend/tests/providers/ultrahuman/test_ultrahuman_strategy.py`

Provider strategy initialization and configuration tests.

#### Test Classes

- **`TestUltrahumanStrategy`** - Strategy setup verification
  - `test_ultrahuman_strategy_initialization()` - Instance creation
  - `test_ultrahuman_strategy_name()` - Provider name
  - `test_ultrahuman_strategy_api_base_url()` - API URL configuration
  - `test_ultrahuman_strategy_display_name()` - Display name
  - `test_ultrahuman_strategy_has_oauth()` - OAuth component
  - `test_ultrahuman_strategy_has_data_247()` - Data component
  - `test_ultrahuman_strategy_has_repositories()` - Repository setup
  - `test_ultrahuman_strategy_icon_url()` - Icon URL

### 5. Automated Verification Script

**File:** `backend/scripts/verify_ultrahuman_integration.py`

Comprehensive verification script that runs all critical checks and provides console output.

#### Verification Checks

1. **Provider Registration Check** - Verifies Ultrahuman is registered in ProviderFactory
2. **OAuth Configuration Check** - Validates environment variables are set
3. **Connected Users Check** - Lists active Ultrahuman connections
4. **Database Schema Check** - Verifies required tables exist
5. **Test Sync Execution** - Runs a 2-day sync test
6. **Sleep Records Verification** - Validates sleep data integrity
7. **Activity Samples Verification** - Validates activity samples data
8. **Summary Report** - Pass/fail summary with colored output

#### Usage

```bash
cd backend
uv run python scripts/verify_ultrahuman_integration.py
```

#### Output

The script provides colored console output:
- ✓ Green checkmarks for passing tests
- ✗ Red X marks for failing tests
- ⚠ Yellow warnings for issues
- ℹ Blue info for details

Example output:
```
╔════════════════════════════════════════╗
║   Ultrahuman Integration Verification   ║
╚════════════════════════════════════════╝

1. Provider Registration Check
============================================================
  ✓ Ultrahuman provider registered in factory
  ✓ data_247 component present
  ✓ OAuth component present

VERIFICATION SUMMARY

  Total checks: 7
  Passed: 7
  Failed: 0

  PASS - Provider Registration
  PASS - OAuth Configuration
  ...
```

### 6. Test Fixtures

**File:** `backend/tests/providers/conftest.py`

Ultrahuman-specific test data fixtures:

- `sample_ultrahuman_sleep_data()` - Complete sleep object with all stages
- `sample_ultrahuman_minimal_sleep()` - Minimal sleep with only date
- `sample_ultrahuman_activity_samples()` - HR, HRV, temperature, steps data
- `sample_ultrahuman_recovery_data()` - Recovery index and scores
- `sample_ultrahuman_api_response()` - Full `/user_data/metrics` response

## Running Tests

### Prerequisites

1. **Database Setup**
   ```bash
   docker compose up -d
   make migrate
   make init  # Optional: seed sample data
   ```

2. **Ultrahuman Credentials**
   Set in `backend/config/.env`:
   ```bash
   ULTRAHUMAN_CLIENT_ID=your-client-id
   ULTRAHUMAN_CLIENT_SECRET=your-client-secret
   ULTRAHUMAN_REDIRECT_URI=https://your-domain.com/api/v1/oauth/ultrahuman/callback
   ULTRAHUMAN_DEFAULT_SCOPE=ring_data cgm_data profile
   ```

   **Note:** Ultrahuman requires HTTPS redirect URIs. Use ngrok for local development:
   ```bash
   ngrok http 8000
   # Update ULTRAHUMAN_REDIRECT_URI with ngrok URL
   ```

3. **Active Connection**
   Ensure at least one user has an active Ultrahuman connection in the database.

### Running All Tests

```bash
cd backend

# Run all Ultrahuman tests
uv run pytest tests/providers/ultrahuman/ -v

# Run with coverage
uv run pytest tests/providers/ultrahuman/ -v --cov=app

# Run specific test file
uv run pytest tests/providers/ultrahuman/test_ultrahuman_integration.py -v

# Run specific test
uv run pytest tests/providers/ultrahuman/test_ultrahuman_integration.py::TestUltrahumanSleepDataIntegration::test_full_sleep_sync_flow -v
```

### Running Tests in Docker

```bash
# Run tests inside Docker container
docker compose exec app uv run pytest tests/providers/ultrahuman/ -v

# Run verification script in Docker
docker compose exec app uv run python scripts/verify_ultrahuman_integration.py
```

### Test Coverage Goals

- Unit tests: 85%+ coverage for `data_247.py`
- Integration tests: 70%+ coverage for sync flow
- Edge cases: 100% of known edge cases covered
- API endpoints: 100% of Ultrahuman endpoints tested

### Continuous Integration

The tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Ultrahuman Tests
  run: |
    cd backend
    uv run pytest tests/providers/ultrahuman/ -v --cov=app --cov-report=xml

- name: Run Verification Script
  run: |
    cd backend
    uv run python scripts/verify_ultrahuman_integration.py
```

## Troubleshooting

### Issue: Tests fail with "No active Ultrahuman connection found"

**Solution:** Ensure you have a user with an active Ultrahuman connection in the database:

```bash
docker compose exec db psql -U open-wearables -d open-wearables -c "
  SELECT u.id, u.email, uc.provider, uc.status
  FROM \"user\" u
  JOIN user_connection uc ON u.id = uc.user_id
  WHERE uc.provider = 'ultrahuman';
"
```

### Issue: OAuth tests fail with "Missing credentials"

**Solution:** Set Ultrahuman environment variables in `backend/config/.env`:

```bash
# Check if variables are set
grep ULTRAHUMAN_ backend/config/.env
```

### Issue: Sync returns 0 for all data types

**Solution:** Check the user has data in Ultrahuman for the sync date range:

```bash
# Check if user wore the device on specific dates
# The script syncs the last 2 days by default
# Adjust if user has no recent data
```

### Issue: Verification script shows "Ultrahuman provider not found in factory"

**Solution:** Ensure Ultrahuman is registered in `backend/app/services/providers/factory.py`:

```python
case "ultrahuman":
    return UltrahumanStrategy()
```

## Development Workflow

### Adding New Tests

1. Create test method in appropriate test class
2. Use Ultrahuman fixtures from `conftest.py`
3. Test both success and failure scenarios
4. Run linting: `uv run ruff check . --fix && uv run ruff format .`
5. Run tests: `uv run pytest tests/providers/ultrahuman/ -v`

### Updating Fixtures

Add new fixtures to `backend/tests/providers/conftest.py`:

```python
@pytest.fixture
def sample_ultrahuman_your_data() -> dict:
    """Sample Ultrahuman your_data."""
    return {
        "date": "2024-01-15",
        "your_field": "your_value",
    }
```

### Modifying Verification Script

Add new verification function to `backend/scripts/verify_ultrahuman_integration.py`:

```python
def check_your_feature() -> bool:
    """Check your feature."""
    print_header("X. Your Feature Check")

    # Your check logic
    return True
```

Add to `main()` function:

```python
results["Your Feature"] = check_your_feature()
```

## Documentation References

- [Integration Testing Guide](../../../test-ultrahuman-integration.md) - Manual testing steps
- [Backend AGENTS.md](../backend/AGENTS.md) - Backend development patterns
- [How to Add New Provider](../../../docs/dev-guides/how-to-add-new-provider.mdx) - Provider architecture

## Support

For issues or questions:
1. Check the [troubleshooting section](#troubleshooting)
2. Review [existing test files](backend/tests/providers/ultrahuman/)
3. Consult [Ultrahuman API documentation](https://vision.ultrahuman.com/developer-docs)
4. Open a GitHub issue
