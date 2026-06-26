-- Remove stable series type definitions.
DELETE FROM series_type_definition
WHERE id IN (
  1, 2, 3, 4, 5, 7,
  20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
  40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51,
  60, 61, 62,
  80, 81, 82, 83, 84, 85, 86, 87,
  100, 101, 102, 103, 104,
  120, 121, 122, 123, 124, 125, 126,
  140, 141, 142, 143, 144, 145, 146,
  160, 161,
  180, 181, 182, 183, 184,
  200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212,
  220, 221, 222, 223,
  500, 501, 502, 503, 504, 505, 506, 507
);

-- Remove default provider settings.
DELETE FROM provider_settings
WHERE provider IN (
  'apple',
  'samsung',
  'google',
  'garmin',
  'polar',
  'suunto',
  'whoop',
  'strava',
  'oura',
  'fitbit',
  'ultrahuman'
);

-- Remove default provider priorities.
DELETE FROM provider_priority
WHERE provider IN (
  'apple',
  'garmin',
  'polar',
  'suunto',
  'whoop'
);

-- Remove default device type priorities.
DELETE FROM device_type_priority
WHERE device_type IN (
  'watch',
  'band',
  'ring',
  'phone',
  'scale',
  'other',
  'unknown'
);

-- Remove default archival settings singleton.
DELETE FROM archival_settings
WHERE id = 1;