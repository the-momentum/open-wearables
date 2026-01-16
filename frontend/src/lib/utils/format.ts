/**
 * Formatting utility functions for dates, durations, and other display values.
 */

/**
 * Format a date string to a localized string representation.
 * Returns 'Never' if the date is null or undefined.
 */
export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return 'Never';
  return new Date(dateString).toLocaleString();
}

/**
 * Format a date string to a localized date (no time).
 * Returns 'Never' if the date is null or undefined.
 */
export function formatDateOnly(dateString: string | null | undefined): string {
  if (!dateString) return 'Never';
  return new Date(dateString).toLocaleDateString();
}

/**
 * Format duration in seconds to a human-readable string.
 * Examples: "45m", "1h 30m", "2h 0m"
 */
export function formatDuration(
  seconds: string | number | null | undefined
): string {
  if (seconds === null || seconds === undefined) return '-';
  const totalSeconds =
    typeof seconds === 'string' ? parseInt(seconds, 10) : seconds;
  if (isNaN(totalSeconds)) return '—';

  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
}

/**
 * Format minutes to a human-readable string.
 * Examples: "45m", "1h 30m"
 */
export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return '-';
  const totalMins = Math.round(minutes);
  const hours = Math.floor(totalMins / 60);
  const mins = totalMins % 60;
  if (hours === 0) return `${mins}m`;
  return `${hours}h ${mins}m`;
}

/**
 * Format a number with locale-specific thousand separators.
 */
export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-';
  return value.toLocaleString();
}

/**
 * Format distance in meters to a human-readable string.
 * Shows km if >= 1000m, otherwise shows meters.
 */
export function formatDistance(meters: number | null | undefined): string {
  if (meters === null || meters === undefined) return '-';
  const km = meters / 1000;
  if (km >= 1) {
    return `${km.toFixed(1)} km`;
  }
  return `${Math.round(meters)} m`;
}

/**
 * Format calories to a string with unit.
 */
export function formatCalories(kcal: number | null | undefined): string {
  if (kcal === null || kcal === undefined) return '-';
  return `${Math.round(Number(kcal))} kcal`;
}

/**
 * Format bedtime from minutes since midnight.
 * Handles wrap-around for late nights (after midnight).
 */
export function formatBedtime(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return '-';
  // Handle wrap-around for late nights
  const normalizedMinutes = minutes >= 1440 ? minutes - 1440 : minutes;
  const hours = Math.floor(normalizedMinutes / 60);
  const mins = Math.round(normalizedMinutes % 60);
  const period = hours >= 12 ? 'PM' : 'AM';
  const displayHours = hours > 12 ? hours - 12 : hours === 0 ? 12 : hours;
  return `${displayHours}:${mins.toString().padStart(2, '0')} ${period}`;
}

/**
 * Format heart rate value with unit.
 */
export function formatHeartRate(bpm: number | null | undefined): string {
  if (bpm === null || bpm === undefined) return '-';
  return `${Math.round(bpm)} bpm`;
}

/**
 * Format percentage value (rounded).
 */
export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-';
  return `${Math.round(value)}%`;
}

/**
 * Format percentage value with one decimal place.
 */
export function formatPercentDecimal(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-';
  return `${value.toFixed(1)}%`;
}

/**
 * Format weight in kg.
 */
export function formatWeight(kg: number | null | undefined): string {
  if (kg === null || kg === undefined) return '-';
  return `${kg.toFixed(1)} kg`;
}

/**
 * Format height in cm.
 */
export function formatHeight(cm: number | null | undefined): string {
  if (cm === null || cm === undefined) return '-';
  return `${Math.round(cm)} cm`;
}

/**
 * Format temperature in Celsius.
 */
export function formatTemperature(celsius: number | null | undefined): string {
  if (celsius === null || celsius === undefined) return '-';
  return `${celsius.toFixed(1)}°C`;
}

/**
 * Format BMI value.
 */
export function formatBmi(bmi: number | null | undefined): string {
  if (bmi === null || bmi === undefined) return '-';
  return bmi.toFixed(1);
}

/**
 * Truncate a UUID/ID to show first 8 and last 4 characters.
 * More useful for UUIDs as it shows both start and end.
 */
export function truncateId(id: string, maxLength = 12): string {
  if (!id) return '—';
  if (id.length <= maxLength) return id;
  return `${id.slice(0, 8)}...${id.slice(-4)}`;
}
