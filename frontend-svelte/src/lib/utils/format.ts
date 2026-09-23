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

/** Trailing zeroes dropped: `74.0 kg` reads as a precision nobody claimed. */
export function formatDecimal(value: number | null, digits = 1): string | null {
	return value === null ? null : value.toFixed(digits).replace(/\.0+$/, '');
}

/** The same, for the many callers that want a string either way. */
export const showDecimal = (value: number | null, digits = 1): string =>
	formatDecimal(value, digits) ?? DASH;

/**
 * en-US, against the en-GB the rest of this file uses: en-GB compact renders
 * "2.3bn" and a lowercase "1m", and an "m" beside a metric reads as a unit.
 */
const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });

/**
 * A big aggregate at a glance: 8_432 → "8.4K", 1_450_000 → "1.5M". Rolls K → M →
 * B at the boundary, so 999_999 is "1M" and never "1000K". Anything under a
 * thousand is shown whole.
 *
 * For counts, not for quantities: a step count or a distance has a precision
 * worth keeping, and `formatNumber` is what keeps it.
 */
export const formatCompact = (value: number | null): string =>
	value === null ? DASH : compact.format(value);

/**
 * A part of a whole, as a percentage. Something present never reads as "0%":
 * 57 KB of archive in a 475 MB database is small, not absent.
 */
export function formatPercent(value: number, whole: number): string {
	if (whole <= 0 || value <= 0) return '0%';
	const percent = (value / whole) * 100;
	return percent < 1 ? '<1%' : `${Math.round(percent)}%`;
}

/** A count and the share of a whole it makes up: "480 · 53%". */
export const formatShare = (value: number, whole: number): string =>
	`${formatNumber(value)} · ${formatPercent(value, whole)}`;

/** The unit a cycle, a trend and an average are all counted in. */
export const formatDays = (value: number): string =>
	`${showDecimal(value)} ${value === 1 ? 'day' : 'days'}`;

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

const date = new Intl.DateTimeFormat('en-GB', {
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

/**
 * The calendar day a reading belongs to, in its own zone — the key a list is
 * grouped by, where `formatLocalDay` is what the group is called.
 */
export function localDayKey(iso: string, zoneOffset: string | null): string {
	const date = inZone(iso, zoneOffset);
	return date ? date.toISOString().slice(0, 10) : '';
}

export function formatLocalDay(iso: string, zoneOffset: string | null): string {
	const date = inZone(iso, zoneOffset);
	return date ? day.format(date) : DASH;
}

/**
 * A calendar date with no weekday, for a record measured in days rather than
 * hours — where which weekday it fell on says nothing.
 */
export function formatLocalDate(iso: string, zoneOffset: string | null): string {
	const at = inZone(iso, zoneOffset);
	return at ? date.format(at) : DASH;
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

const BYTE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];

/**
 * Base 1024 with the backend's unit names, so a size read here and one read
 * off the API agree. One decimal: storage is an estimate, and a second digit
 * claims a precision nobody has.
 */
export function formatBytes(bytes: number): string {
	if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
	const step = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), BYTE_UNITS.length - 1);
	return step === 0
		? `${Math.round(bytes)} B`
		: `${(bytes / 1024 ** step).toFixed(1)} ${BYTE_UNITS[step]}`;
}
