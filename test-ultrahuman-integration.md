# Ultrahuman Integration Testing Guide

This document provides a comprehensive testing procedure for the Ultrahuman integration. Follow these steps to verify that the integration is working correctly and all data is being properly synced and stored.

## Ultrahuman Testing Agent

The project includes a specialized testing agent for Ultrahuman integration with:

### Test Files

- **`backend/tests/providers/ultrahuman/test_ultrahuman_integration.py`** - End-to-end integration tests using real API calls
- **`backend/tests/providers/ultrahuman/test_ultrahuman_data_247.py`** - Unit tests for data normalization
- **`backend/tests/providers/ultrahuman/test_ultrahuman_oauth.py`** - OAuth flow tests
- **`backend/tests/providers/ultrahuman/test_ultrahuman_strategy.py`** - Provider strategy tests

### Automated Verification Script

**`backend/scripts/verify_ultrahuman_integration.py`** - Comprehensive verification with console output

```bash
cd backend
uv run python scripts/verify_ultrahuman_integration.py
```

This script runs:
1. Provider registration check
2. OAuth configuration validation
3. Connected users verification
4. Database schema validation
5. Test sync execution
6. Sleep records verification
7. Activity samples verification
8. Summary report with pass/fail status

### Test Fixtures

Ultrahuman-specific fixtures in `backend/tests/providers/conftest.py`:

- `sample_ultrahuman_sleep_data()` - Complete sleep with all stages
- `sample_ultrahuman_minimal_sleep()` - Minimal sleep data
- `sample_ultrahuman_activity_samples()` - HR, HRV, temp, steps
- `sample_ultrahuman_recovery_data()` - Recovery metrics
- `sample_ultrahuman_api_response()` - Full API response

---

## Prerequisites

- Docker and Docker Compose installed
- Server running (`docker compose up -d`)
- At least one Ultrahuman user connected to the platform
- Access to the database and API

## Table of Contents

1. [Verify Connected Users](#1-verify-connected-users)
2. [Test Data Sync](#2-test-data-sync)
3. [Verify Database Storage](#3-verify-database-storage)
4. [Test API Endpoints](#4-test-api-endpoints)
5. [Common Issues and Solutions](#5-common-issues-and-solutions)

---

## 1. Verify Connected Users

### Check for Ultrahuman Connected Users

```bash
docker compose exec db psql -U open-wearables -d open-wearables -c "
  SELECT 
    u.id, 
    u.email, 
    uc.provider, 
    uc.status, 
    uc.created_at, 
    uc.last_synced_at 
  FROM \"user\" u 
  JOIN user_connection uc ON u.id = uc.user_id 
  WHERE uc.provider = 'ultrahuman';
"
```

**Expected Output:**
- At least one user with `status = 'active'`
- `last_synced_at` should show recent sync activity (if automatic sync is enabled)

**Example:**
```
                  id                  |        email        |  provider  | status |          created_at           |        last_synced_at         
--------------------------------------+---------------------+------------+--------+-------------------------------+-------------------------------
 3f708058-407a-4809-ab84-c84b50fd2e6b | example@example.com | ultrahuman | active | 2026-01-14 19:17:43.547342+00 | 2026-01-15 17:18:49.816159+00
```

### Get External Device Mapping

Save the user ID for later use, then get the device mapping:

```bash
# Replace USER_ID with actual user ID from previous query
docker compose exec db psql -U open-wearables -d open-wearables -c "
  SELECT id, provider_name, user_id 
  FROM external_device_mapping 
  WHERE user_id = 'USER_ID' AND provider_name = 'ultrahuman';
"
```

**Expected Output:**
- One mapping record with `provider_name = 'ultrahuman'`

---

## 2. Test Data Sync

### Manual Sync via Python Script

Create a test sync for the last 3 days:

```bash
docker compose exec app python -c "
from datetime import datetime, timedelta, timezone
from uuid import UUID
from app.database import SessionLocal
from app.services.providers.factory import ProviderFactory

# Replace with your user ID
USER_ID = UUID('3f708058-407a-4809-ab84-c84b50fd2e6b')
PROVIDER = 'ultrahuman'

db = SessionLocal()
try:
    factory = ProviderFactory()
    strategy = factory.get_provider(PROVIDER)
    
    if strategy.data_247:
        # Sync last 3 days
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=2)
        
        print(f'Syncing Ultrahuman data from {start_time.date()} to {end_time.date()}...')
        
        provider_impl = strategy.data_247
        results = provider_impl.load_and_save_all(db, USER_ID, start_time=start_time, end_time=end_time)
        
        print('\nSync Results:')
        for key, value in results.items():
            print(f'  {key}: {value}')
        
        db.commit()
        print('\nSync completed successfully!')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
finally:
    db.close()
"
```

**Expected Output:**
```
Syncing Ultrahuman data from 2026-01-13 to 2026-01-15...

Sync Results:
  sleep_sessions_synced: 3
  activity_samples: 1800+
  recovery_days_synced: 0

Sync completed successfully!
```

**Key Metrics:**
- `sleep_sessions_synced`: Should match the number of days with sleep data (1-3)
- `activity_samples`: Should be 500-700+ samples per day (heart rate, HRV, temperature, steps)
- `recovery_days_synced`: Currently 0 (recovery data not implemented yet)

### Test Raw API Response

Verify the Ultrahuman API is returning data correctly:

```bash
docker compose exec app python -c "
from datetime import datetime, timedelta, timezone
from uuid import UUID
from app.database import SessionLocal
from app.services.providers.factory import ProviderFactory
import json

USER_ID = UUID('3f708058-407a-4809-ab84-c84b50fd2e6b')
PROVIDER = 'ultrahuman'

db = SessionLocal()
try:
    factory = ProviderFactory()
    strategy = factory.get_provider(PROVIDER)
    provider_impl = strategy.data_247
    
    # Get yesterday's date
    date = datetime.now(timezone.utc) - timedelta(days=1)
    date_str = date.strftime('%Y-%m-%d')
    
    print(f'Fetching data for {date_str}...')
    
    response = provider_impl._make_api_request(
        db, USER_ID, '/user_data/metrics', params={'date': date_str}
    )
    
    if response and 'data' in response and 'metric_data' in response['data']:
        metrics = response['data']['metric_data']
        print(f'\nReceived {len(metrics)} metric types:')
        for item in metrics:
            metric_type = item.get('type')
            print(f'  - {metric_type}')
            
            # Check Sleep data structure
            if metric_type == 'Sleep':
                sleep_obj = item['object']
                has_stages = 'sleep_stages' in sleep_obj
                has_quick_metrics = 'quick_metrics' in sleep_obj
                print(f'    ✓ sleep_stages present: {has_stages}')
                print(f'    ✓ quick_metrics present: {has_quick_metrics}')
                
                if has_stages:
                    for stage in sleep_obj['sleep_stages']:
                        print(f'      - {stage[\"type\"]}: {stage[\"stage_time\"]}s')
    else:
        print('No data returned from API!')
        
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
finally:
    db.close()
"
```

**Expected Output:**
```
Fetching data for 2026-01-14...

Received 7 metric types:
  - hr
  - temp
  - hrv
  - steps
  - night_rhr
  - avg_sleep_hrv
  - Sleep
    ✓ sleep_stages present: True
    ✓ quick_metrics present: True
      - deep_sleep: 3000s
      - light_sleep: 16500s
      - rem_sleep: 5700s
      - awake: 1920s
```

---

## 3. Verify Database Storage

### Check Sleep Records

Verify sleep records are stored with complete data:

```bash
# Replace MAPPING_ID with the external_device_mapping_id from section 1
docker compose exec db psql -U open-wearables -d open-wearables -c "
  SELECT 
    er.start_datetime,
    sd.sleep_total_duration_minutes,
    sd.sleep_deep_minutes,
    sd.sleep_light_minutes,
    sd.sleep_rem_minutes,
    sd.sleep_awake_minutes,
    sd.sleep_efficiency_score
  FROM event_record er
  JOIN sleep_details sd ON er.id = sd.record_id
  WHERE er.external_device_mapping_id = 'MAPPING_ID'
    AND er.start_datetime >= CURRENT_DATE - INTERVAL '7 days'
  ORDER BY er.start_datetime DESC
  LIMIT 5;
"
```

**Expected Output:**
```
     start_datetime     | sleep_total_duration_minutes | sleep_deep_minutes | sleep_light_minutes | sleep_rem_minutes | sleep_awake_minutes | sleep_efficiency_score 
------------------------+------------------------------+--------------------+---------------------+-------------------+---------------------+------------------------
 2026-01-15 01:24:00+00 |                          442 |                 54 |                 319 |                69 |                  49 |                  90.00
 2026-01-14 02:04:00+00 |                          420 |                 50 |                 275 |                95 |                  32 |                  93.00
 2026-01-13 01:24:00+00 |                          387 |                 64 |                 238 |                85 |                  38 |                  91.00
```

**Critical Checks:**
- ✅ All sleep stage minutes should be **non-zero** (if showing 0, the sleep_stages parsing is broken)
- ✅ `sleep_efficiency_score` should be present (not NULL)
- ✅ Sleep stages should add up approximately to `sleep_total_duration_minutes`

### Check Activity Samples (Timeseries Data)

Verify activity samples are being saved:

```bash
docker compose exec db psql -U open-wearables -d open-wearables -c "
  SELECT 
    std.code,
    std.unit,
    COUNT(*) as count,
    MIN(dps.recorded_at) as earliest,
    MAX(dps.recorded_at) as latest
  FROM data_point_series dps
  JOIN series_type_definition std ON dps.series_type_definition_id = std.id
  WHERE dps.external_device_mapping_id = 'MAPPING_ID'
    AND dps.recorded_at >= CURRENT_DATE - INTERVAL '3 days'
  GROUP BY std.code, std.unit
  ORDER BY count DESC;
"
```

**Expected Output:**
```
            code             |  unit   | count |        earliest        |         latest         
-----------------------------+---------+-------+------------------------+------------------------
 body_temperature            | celsius |   605 | 2026-01-13 00:02:04+00 | 2026-01-15 09:36:49+00
 heart_rate                  | bpm     |   604 | 2026-01-13 00:04:38+00 | 2026-01-15 09:34:23+00
 heart_rate_variability_sdnn | ms      |   417 | 2026-01-13 00:04:38+00 | 2026-01-15 09:29:24+00
 steps                       | count   |   173 | 2026-01-13 00:12:04+00 | 2026-01-15 09:36:49+00
```

**Critical Checks:**
- ✅ All 4 data types should be present: `body_temperature`, `heart_rate`, `heart_rate_variability_sdnn`, `steps`
- ✅ Sample counts should be reasonable (500-700+ per day for HR, temp, HRV; fewer for steps)
- ✅ If count is 0 for all types, the activity sample saving is broken

### Count Total Records

Quick count of all Ultrahuman data:

```bash
docker compose exec db psql -U open-wearables -d open-wearables -c "
  -- Sleep records
  SELECT 
    'Sleep Records' as data_type,
    COUNT(*) as count
  FROM event_record
  WHERE external_device_mapping_id = 'MAPPING_ID'
    AND category = 'sleep'
  
  UNION ALL
  
  -- Activity samples
  SELECT 
    'Activity Samples' as data_type,
    COUNT(*) as count
  FROM data_point_series
  WHERE external_device_mapping_id = 'MAPPING_ID';
"
```

---

## 4. Test API Endpoints

### Get Authentication Token

```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@admin.com&password=secret123" | \
  python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "Token obtained: ${TOKEN:0:20}..."
```

### Test Sleep Events Endpoint

```bash
curl -s "http://localhost:8000/api/v1/users/USER_ID/events/sleep?start_date=2026-01-13&end_date=2026-01-16&limit=3" \
  -H "Authorization: Bearer $TOKEN" | \
  python -m json.tool
```

**Expected Output:**
```json
{
    "data": [
        {
            "id": "...",
            "start_time": "2026-01-15T01:24:00Z",
            "end_time": "2026-01-15T09:34:00Z",
            "source": {
                "provider": "ultrahuman",
                "device": null
            },
            "duration_seconds": 29400,
            "efficiency_percent": 90.0,
            "stages": {
                "awake_minutes": 49,
                "light_minutes": 319,
                "deep_minutes": 54,
                "rem_minutes": 69
            },
            "is_nap": false
        }
    ],
    "pagination": {
        "total_count": 3
    }
}
```

**Critical Checks:**
- ✅ `efficiency_percent` should not be `null`
- ✅ All `stages` values should be **non-zero** (not 0)
- ✅ `stages` should have all 4 keys: `awake_minutes`, `light_minutes`, `deep_minutes`, `rem_minutes`

### Test Heart Rate Timeseries Endpoint

```bash
curl -s "http://localhost:8000/api/v1/users/USER_ID/timeseries?start_time=2026-01-14T00:00:00Z&end_time=2026-01-14T02:00:00Z&types=heart_rate&limit=5" \
  -H "Authorization: Bearer $TOKEN" | \
  python -m json.tool
```

**Expected Output:**
```json
{
    "data": [
        {
            "timestamp": "2026-01-14T00:09:29Z",
            "type": "heart_rate",
            "value": 78.0,
            "unit": "bpm"
        },
        {
            "timestamp": "2026-01-14T00:14:30Z",
            "type": "heart_rate",
            "value": 97.0,
            "unit": "bpm"
        }
    ],
    "pagination": {
        "total_count": 19
    }
}
```

**Critical Checks:**
- ✅ Data array should not be empty
- ✅ Values should be realistic (40-200 bpm for heart rate)

### Test Multiple Timeseries Types

```bash
curl -s "http://localhost:8000/api/v1/users/USER_ID/timeseries?start_time=2026-01-14T00:00:00Z&end_time=2026-01-14T02:00:00Z&types=heart_rate_variability_sdnn&types=body_temperature&types=steps&limit=10" \
  -H "Authorization: Bearer $TOKEN" | \
  python -m json.tool
```

**Expected Output:**
Should return a mix of HRV, temperature, and steps data.

---

## 5. Common Issues and Solutions

### Issue 1: Sleep Stages All Show 0

**Symptoms:**
```
sleep_deep_minutes: 0
sleep_light_minutes: 0
sleep_rem_minutes: 0
sleep_awake_minutes: 0
```

**Root Cause:**
The code is reading sleep stages from the wrong location in the API response.

**Solution:**
Check `backend/app/services/providers/ultrahuman/data_247.py` around line 117-124. Ensure it reads from `sleep_stages` array, not `quick_metrics`:

```python
# CORRECT - reads from sleep_stages
sleep_stages = {s.get("type"): s.get("stage_time", 0) for s in raw_sleep.get("sleep_stages", [])}
deep_seconds = sleep_stages.get("deep_sleep", 0) or 0
rem_seconds = sleep_stages.get("rem_sleep", 0) or 0
light_seconds = sleep_stages.get("light_sleep", 0) or 0
awake_seconds = sleep_stages.get("awake", 0) or 0

# WRONG - reads from quick_metrics (won't find the data)
quick_metrics = {m.get("type"): m.get("value", 0) for m in raw_sleep.get("quick_metrics", [])}
deep_seconds = quick_metrics.get("deep_sleep", 0) or 0  # ❌ NOT FOUND
```

**Fix and Re-sync:**
1. Fix the code in `data_247.py`
2. Copy the file to the container (if docker sync not working):
   ```bash
   docker cp backend/app/services/providers/ultrahuman/data_247.py \
     backend__open-wearables:/root_project/app/services/providers/ultrahuman/data_247.py
   ```
3. Restart the app:
   ```bash
   docker compose restart app celery-worker
   ```
4. Delete old sleep records and re-sync:
   ```bash
   docker compose exec db psql -U open-wearables -d open-wearables -c "
     DELETE FROM event_record 
     WHERE external_device_mapping_id = 'MAPPING_ID' 
       AND start_datetime >= 'START_DATE';
   "
   ```
5. Re-run the sync script from Section 2

### Issue 2: No Activity Samples in Database

**Symptoms:**
```
activity_samples_synced: 0
```
Or timeseries API returns empty data.

**Root Cause:**
- Database constraint violations (e.g., missing series_type_definition)
- Errors in `save_activity_samples` method being silently ignored

**Solution:**

1. **Check logging level** - Ensure errors are logged at WARNING level:
   ```python
   # In data_247.py, around line 395
   self.logger.warning(f"Failed to save {key} sample for user {user_id} at {recorded_at_str}: {e}")
   ```

2. **Check app logs** for errors:
   ```bash
   docker compose logs app --tail 100 | grep -i "failed to save"
   ```

3. **Verify series type definitions exist** in database:
   ```bash
   docker compose exec db psql -U open-wearables -d open-wearables -c "
     SELECT id, code, unit 
     FROM series_type_definition 
     WHERE code IN ('heart_rate', 'heart_rate_variability_sdnn', 'body_temperature', 'steps');
   "
   ```

### Issue 3: Docker File Sync Not Working

**Symptoms:**
Code changes on host don't appear in the container.

**Solution:**
Manually copy the file:
```bash
docker cp backend/app/services/providers/ultrahuman/data_247.py \
  backend__open-wearables:/root_project/app/services/providers/ultrahuman/data_247.py

docker compose restart app celery-worker
```

Verify the file was updated:
```bash
docker compose exec app ls -la /root_project/app/services/providers/ultrahuman/data_247.py
```

### Issue 4: 404 Errors from Ultrahuman API

**Symptoms:**
```
Ultrahuman API error for user ...: 404 - {"status":404,"error":"Not Found"}
```

**Possible Causes:**

1. **Requesting future dates**: Ultrahuman API returns 404 for dates that haven't occurred yet
   - Solution: Sync yesterday or earlier dates

2. **Invalid date format**: Ensure date is in `YYYY-MM-DD` format
   - Solution: Check `date.strftime('%Y-%m-%d')` in code

3. **Token expired**: User's access token may have expired
   - Solution: Check `token_expires_at` in `user_connection` table
   - Re-authenticate user if needed

4. **No data for that date**: User didn't wear the device
   - This is normal - the sync should continue with other dates

### Issue 5: Sleep Efficiency is NULL

**Symptoms:**
```
sleep_efficiency_score: null
```

**Root Cause:**
The code is looking for efficiency in the wrong place in the API response.

**Solution:**
Check that the code reads from `quick_metrics` with type `"sleep_efic"`:

```python
# CORRECT
efficiency = quick_metrics.get("sleep_efic")
if efficiency is None:
    efficiency = raw_sleep.get("sleep_efficiency")
```

---

## Quick Test Checklist

Use this checklist to quickly verify the integration:

- [ ] Connected user exists with `status = 'active'`
- [ ] Manual sync completes successfully with `sleep_sessions_synced > 0`
- [ ] Manual sync shows `activity_samples > 500` per day
- [ ] Sleep records in database have **non-zero** sleep stage values
- [ ] Sleep efficiency scores are present (not NULL)
- [ ] Activity samples exist for all 4 types (HR, HRV, temp, steps)
- [ ] Sleep API endpoint returns data with populated stages
- [ ] Timeseries API endpoint returns heart rate data
- [ ] Timeseries API endpoint returns HRV and temperature data

---

## Testing Different Scenarios

### Test Historical Data Sync

Sync older data (last 30 days):

```bash
docker compose exec app python -c "
from datetime import datetime, timedelta, timezone
from uuid import UUID
from app.database import SessionLocal
from app.services.providers.factory import ProviderFactory

USER_ID = UUID('USER_ID_HERE')
db = SessionLocal()

try:
    factory = ProviderFactory()
    strategy = factory.get_provider('ultrahuman')
    provider_impl = strategy.data_247
    
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=30)
    
    print(f'Syncing 30 days of data...')
    results = provider_impl.load_and_save_all(db, USER_ID, start_time, end_time)
    
    print(f'Sleep sessions: {results[\"sleep_sessions_synced\"]}')
    print(f'Activity samples: {results[\"activity_samples\"]}')
    
    db.commit()
finally:
    db.close()
"
```

### Test Incremental Sync

Sync only today's data:

```bash
docker compose exec app python -c "
from datetime import datetime, timezone
from uuid import UUID
from app.database import SessionLocal
from app.services.providers.factory import ProviderFactory

USER_ID = UUID('USER_ID_HERE')
db = SessionLocal()

try:
    factory = ProviderFactory()
    strategy = factory.get_provider('ultrahuman')
    provider_impl = strategy.data_247
    
    now = datetime.now(timezone.utc)
    
    results = provider_impl.load_and_save_all(db, USER_ID, now, now)
    print(f'Results: {results}')
    
    db.commit()
finally:
    db.close()
"
```

---

## Notes for Future Developers

1. **Ultrahuman API Response Structure**:
   - Sleep stages are in `sleep_stages` array, NOT in `quick_metrics`
   - Sleep efficiency is in `quick_metrics` with type `"sleep_efic"`
   - Activity data comes in separate metric types: `hr`, `hrv`, `temp`, `steps`

2. **Database Schema**:
   - Sleep data is stored in `event_record` + `sleep_details` tables
   - Activity samples are stored in `data_point_series` table
   - Both link to `external_device_mapping` table (not directly to user)

3. **Important Files**:
   - `backend/app/services/providers/ultrahuman/data_247.py` - Main sync logic
   - `backend/app/services/providers/ultrahuman/oauth.py` - OAuth implementation
   - `backend/app/services/providers/ultrahuman/strategy.py` - Provider registration

4. **Testing After Code Changes**:
   - Always restart both `app` and `celery-worker` containers
   - Delete and re-sync recent records to test fixes
   - Verify both database storage AND API endpoint responses

5. **Data Volume Expectations**:
   - Sleep: 1 record per night (if user wore the device)
   - Heart rate: ~120 samples per day (every ~5-10 minutes)
   - Temperature: ~100-200 samples per day
   - HRV: ~80-100 samples per day
   - Steps: ~150-200 samples per day (5-minute intervals)
