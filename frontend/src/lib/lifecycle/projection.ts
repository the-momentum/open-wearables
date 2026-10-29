import type { ArchivalSettings, Policy, StorageEstimate } from './types';
import { isWholeIn } from '$lib/utils/numbers';

export const PROJECTION_MONTHS = 18;
export const DAYS_PER_MONTH = 30;

/**
 * An assumption, not a measurement: a series sampled once a minute is ~1440
 * rows a day as samples and one row a day rolled up. Carried over from the old
 * dashboard, and said on the page as an assumption.
 */
export const ROLLUP_RATIO = 1 / 500;

/** How the page says it, so the copy cannot drift from the number the maths uses. */
export const ROLLUP_RATIO_LABEL = `1/${Math.round(1 / ROLLUP_RATIO)}`;

export const policyOf = (settings: ArchivalSettings): Policy => ({
	rollup: settings.rollup_enabled,
	retain: settings.delete_after_days
});

export const settingsOf = (policy: Policy): ArchivalSettings => ({
	rollup_enabled: policy.rollup,
	delete_after_days: policy.retain
});

export const samePolicy = (a: Policy, b: Policy) => a.rollup === b.rollup && a.retain === b.retain;

/**
 * The draft as the save bar posts it and the action reads it back: blank for
 * off. Both ends live here so the two cannot disagree about the encoding.
 */
export const toFields = (policy: Policy): Record<string, string> => ({
	rollup: policy.rollup ? 'on' : '',
	retain: policy.retain === null ? '' : String(policy.retain)
});

export function fromFields(form: FormData): Policy {
	const raw = String(form.get('retain') ?? '').trim();
	return { rollup: form.get('rollup') === 'on', retain: raw === '' ? null : Number(raw) };
}

/** The API's bound, so the form refuses what the PUT would. */
export const LIMITS = { retain: 7300 } as const;

export type Growth = 'bounded' | 'linear_efficient' | 'linear';

/** The same rule the backend uses for `growth_class`, applied to the draft. */
export const growthOf = (policy: Policy): Growth =>
	policy.retain === null ? 'linear' : policy.rollup ? 'linear_efficient' : 'bounded';

export const liveBytes = (storage: StorageEstimate) =>
	storage.live_data_bytes + storage.live_index_bytes;

export const aggregateBytes = (storage: StorageEstimate) =>
	storage.aggregate_data_bytes + storage.aggregate_index_bytes;

/**
 * Live size over the days it covers. A backfill stretches the span and so
 * lowers the rate, which is why this is labelled an estimate wherever it shows.
 */
export const dailyIngest = (storage: StorageEstimate): number =>
	storage.live_row_count === 0 ? 0 : liveBytes(storage) / Math.max(storage.live_data_span_days, 1);

/**
 * Day by day, one point a month:
 * - samples grow by the daily ingest, capped at the deletion window when deletion is on;
 * - with rollup on, every day adds its rolled-up rows, which deletion leaves in place.
 *
 * Other tables are left out: nothing here changes them, and they would only
 * lift the whole curve.
 */
export function project(
	storage: StorageEstimate,
	policy: Policy
): { month: number; bytes: number }[] {
	const start = liveBytes(storage) + aggregateBytes(storage);
	const months = Array.from({ length: PROJECTION_MONTHS + 1 }, (_, month) => month);

	if (storage.live_row_count === 0) return months.map((month) => ({ month, bytes: start }));

	const daily = dailyIngest(storage);
	let live = liveBytes(storage);
	let aggregate = aggregateBytes(storage);
	const points: { month: number; bytes: number }[] = [];

	for (let day = 0; day <= PROJECTION_MONTHS * DAYS_PER_MONTH; day++) {
		if (day % DAYS_PER_MONTH === 0) {
			points.push({ month: day / DAYS_PER_MONTH, bytes: Math.round(live + aggregate) });
		}

		live += daily;
		if (policy.rollup) aggregate += daily * ROLLUP_RATIO;
		if (policy.retain !== null) live = Math.min(live, policy.retain * daily);
	}

	return points;
}

/** What stops the draft being saved at all. */
export function invalid(policy: Policy): string | null {
	if (policy.retain !== null && !isWholeIn(policy.retain, 1, LIMITS.retain)) {
		return `Delete after must be a whole number of days, 1 to ${LIMITS.retain}.`;
	}
	return null;
}
