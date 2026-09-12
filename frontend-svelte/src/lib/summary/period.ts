export type PeriodMode = 'all' | 'day' | 'range';

/** Inclusive `YYYY-MM-DD` bounds; both null means the user's whole history. */
export type Period = { mode: PeriodMode; from: string | null; to: string | null };

export const ALL_TIME: Period = { mode: 'all', from: null, to: null };

const DAY = /^\d{4}-\d{2}-\d{2}$/;

const clean = (raw: string | null) => (raw && DAY.test(raw) ? raw : null);

export function parsePeriod(params: URLSearchParams): Period {
	const first = clean(params.get('from'));
	const second = clean(params.get('to'));
	if (!first && !second) return ALL_TIME;

	// One bound alone means that single day, and an inverted pair is a typo.
	const [from, to] = [first ?? second!, second ?? first!].sort();
	return { mode: from === to ? 'day' : 'range', from, to };
}

export function periodParams(period: Period): URLSearchParams {
	const params = new URLSearchParams();
	if (period.from) params.set('from', period.from);
	if (period.to) params.set('to', period.to);
	return params;
}

export const todayIso = (now = new Date()) => now.toISOString().slice(0, 10);

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
	return Math.round((window.to.getTime() - window.from.getTime()) / 86_400_000);
}

/** Daily cells stop being readable — and stop fitting — past a few months. */
export function periodBucket(period: Period): 'day' | 'week' {
	const span = spanDays(period);
	return span !== null && span <= 120 ? 'day' : 'week';
}

/** The day a `day` or `range` picker should start from when none is chosen. */
export function defaultRange(now = new Date()): Period {
	const to = new Date(now);
	const from = new Date(now);
	from.setUTCDate(from.getUTCDate() - 89);
	return { mode: 'range', from: todayIso(from), to: todayIso(to) };
}

/** False for a single day, where a timeline would be one column. */
export const plottable = (period: Period): boolean => {
	const span = spanDays(period);
	return span === null || span > 1;
};
