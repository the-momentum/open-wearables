/** A missing value is a fact about the provider, not a zero. */
export const DASH = '—';

export function formatDuration(seconds: number | null): string {
	if (seconds === null || seconds <= 0) return DASH;

	const minutes = Math.round(seconds / 60);
	const hours = Math.floor(minutes / 60);
	return hours > 0 ? `${hours}h ${minutes % 60}m` : `${minutes}m`;
}

export function formatDistance(meters: number | null): string {
	if (meters === null || meters <= 0) return DASH;
	return meters >= 1000 ? `${(meters / 1000).toFixed(2)} km` : `${Math.round(meters)} m`;
}

/** Backend derives this from distance and moving time, so the unit is trustworthy. */
export function formatPace(secondsPerKm: number | null): string {
	if (secondsPerKm === null || secondsPerKm <= 0) return DASH;

	const whole = Math.round(secondsPerKm);
	return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')} /km`;
}

export const formatNumber = (value: number | null, unit = ''): string =>
	value === null ? DASH : `${Math.round(value).toLocaleString('en-GB')}${unit}`;

// Everything is shifted into the workout's own offset and then read as UTC, so
// the formatter never applies the reader's zone on top.
const clock = new Intl.DateTimeFormat('en-GB', {
	hour: '2-digit',
	minute: '2-digit',
	timeZone: 'UTC'
});

const weekday = new Intl.DateTimeFormat('en-GB', { weekday: 'short', timeZone: 'UTC' });

const day = new Intl.DateTimeFormat('en-GB', {
	weekday: 'short',
	day: 'numeric',
	month: 'short',
	year: 'numeric',
	timeZone: 'UTC'
});

/** Minutes to add to UTC, from a `+01:00` / `-05:30` offset. */
function offsetMinutes(zoneOffset: string | null): number {
	if (!zoneOffset) return 0;
	const [hours, minutes] = zoneOffset.slice(1).split(':').map(Number);
	if (Number.isNaN(hours) || Number.isNaN(minutes)) return 0;
	return (zoneOffset.startsWith('-') ? -1 : 1) * (hours * 60 + minutes);
}

/**
 * The wall clock the workout was recorded against, not the reader's: a run at
 * 07:00 in Warsaw must not read as 06:00 because the admin sits in London. No
 * offset means the provider never told us one, so UTC is all we can honestly show.
 */
function inZone(iso: string, zoneOffset: string | null): Date | null {
	const date = new Date(iso);
	if (Number.isNaN(date.getTime())) return null;
	return new Date(date.getTime() + offsetMinutes(zoneOffset) * 60_000);
}

export function formatLocalTime(iso: string, zoneOffset: string | null): string {
	const date = inZone(iso, zoneOffset);
	if (!date) return DASH;
	// Marked, because an unmarked 07:12 would be read as the athlete's morning
	// when it is only the instant we stored.
	return zoneOffset ? clock.format(date) : `${clock.format(date)} UTC`;
}

export function formatLocalDay(iso: string, zoneOffset: string | null): string {
	const date = inZone(iso, zoneOffset);
	return date ? day.format(date) : DASH;
}

export type LocalRange = {
	/** The two ends fall on different days in the session's own zone. */
	crosses: boolean;
	from: string;
	to: string;
	fromDay: string;
	toDay: string;
	/** No offset was stored, so both ends are UTC and should say so. */
	utc: boolean;
};

/**
 * A range in the session's own zone, in parts, so a caller can style the clock
 * times apart from the days — and choose which end wears its weekday. Without
 * one, a range that crosses midnight reads as running backwards, which is what
 * a US offset did to the old dashboard.
 */
export function localRange(fromIso: string, toIso: string, zoneOffset: string | null): LocalRange {
	const from = inZone(fromIso, zoneOffset);
	const to = inZone(toIso, zoneOffset);
	const blank = { crosses: false, from: DASH, to: DASH, fromDay: '', toDay: '', utc: false };
	if (!from || !to) return blank;

	return {
		crosses: from.toISOString().slice(0, 10) !== to.toISOString().slice(0, 10),
		from: clock.format(from),
		to: clock.format(to),
		fromDay: weekday.format(from),
		toDay: weekday.format(to),
		utc: !zoneOffset
	};
}
