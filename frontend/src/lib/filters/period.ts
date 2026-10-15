import { isoDay } from '$lib/utils/datetime';

export type PeriodMode = 'all' | 'day' | 'range';

/** Inclusive `YYYY-MM-DD` bounds; both null means the user's whole history. */
export type Period = { mode: PeriodMode; from: string | null; to: string | null };

export const ALL_TIME: Period = { mode: 'all', from: null, to: null };

/** One day in milliseconds, for the arithmetic every window does. */
export const DAY_MS = 86_400_000;

const DAY = /^\d{4}-\d{2}-\d{2}$/;

const clean = (raw: string | null) => (raw && DAY.test(raw) ? raw : null);

/** "All time" is asked for by name, so it survives on a tab whose default is narrower. */
const ALL_TIME_PARAM = ['period', 'all'] as const;

/** The last `days` days, today included. */
export function lastDays(days: number, now = new Date()): Period {
	const from = new Date(now);
	from.setUTCDate(from.getUTCDate() - (days - 1));
	return { mode: 'range', from: todayIso(from), to: todayIso(now) };
}

export const RANGE_PRESETS = [
	{ label: '1W', days: 7 },
	{ label: '1M', days: 30 },
	{ label: '3M', days: 90 },
	{ label: '6M', days: 180 },
	{ label: '1Y', days: 365 }
] as const;

/** The preset a period is, or '' for dates picked by hand. */
export const matchingPreset = (period: Period, now = new Date()): string =>
	RANGE_PRESETS.find(({ days }) => {
		const preset = lastDays(days, now);
		return preset.from === period.from && preset.to === period.to;
	})?.label ?? '';

/** Paginated tabs show everything by default; the aggregate-only ones pass a narrower window. */
export function parsePeriod(params: URLSearchParams, fallback: Period = ALL_TIME): Period {
	const first = clean(params.get('from'));
	const second = clean(params.get('to'));
	if (!first && !second)
		return params.get(ALL_TIME_PARAM[0]) === ALL_TIME_PARAM[1] ? ALL_TIME : fallback;

	// One bound alone means that single day, and an inverted pair is a typo.
	const [from, to] = [first ?? second!, second ?? first!].sort();
	return { mode: from === to ? 'day' : 'range', from, to };
}

/** The URL changes that select `period`, for a link or a filter. */
export const periodChanges = (period: Period): Record<string, string | null> => ({
	from: period.from,
	to: period.to,
	[ALL_TIME_PARAM[0]]: period.mode === 'all' ? ALL_TIME_PARAM[1] : null
});

export function periodParams(period: Period): URLSearchParams {
	const params = new URLSearchParams();
	if (period.mode === 'all') params.set(...ALL_TIME_PARAM);
	if (period.from) params.set('from', period.from);
	if (period.to) params.set('to', period.to);
	return params;
}

export const todayIso = (now = new Date()) => isoDay(now);

/** Postgres truncates weeks to Monday, so a week grid has to start there too. */
export function weekStart(date: Date): Date {
	const start = new Date(date);
	start.setUTCHours(0, 0, 0, 0);
	// getUTCDay: 0 is Sunday, so Sunday is six days into its week, not zero.
	start.setUTCDate(start.getUTCDate() - ((start.getUTCDay() + 6) % 7));
	return start;
}

/** Half-open `[from, to)` in UTC, so the final day is included. */
export function periodWindow(period: Period): { from: Date; to: Date } | null {
	if (!period.from || !period.to) return null;

	const to = new Date(`${period.to}T00:00:00Z`);
	to.setUTCDate(to.getUTCDate() + 1);
	return { from: new Date(`${period.from}T00:00:00Z`), to };
}

export function spanDays(period: Period): number | null {
	const window = periodWindow(period);
	if (!window) return null;
	return Math.round((window.to.getTime() - window.from.getTime()) / DAY_MS);
}

/** Daily cells stop being readable - and stop fitting - past a few months. */
export function periodBucket(period: Period): 'day' | 'week' {
	const span = spanDays(period);
	return span !== null && span <= 120 ? 'day' : 'week';
}

/** The day a `day` or `range` picker should start from when none is chosen. */
export const defaultRange = (now = new Date()) => lastDays(90, now);

/** False for a single day, where a timeline would be one column. */
export const plottable = (period: Period): boolean => {
	const span = spanDays(period);
	return span === null || span > 1;
};
