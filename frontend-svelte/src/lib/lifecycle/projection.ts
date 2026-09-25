import type { ArchivalSettings, Policy, StorageEstimate } from './types';
import { isWholeIn } from '$lib/utils/numbers';

export const PROJECTION_MONTHS = 18;
export const DAYS_PER_MONTH = 30;

/**
 * An assumption, not a measurement: a series sampled once a minute is ~1440
 * rows a day live and one row a day archived. Carried over from the old
 * dashboard, and said on the page as an assumption.
 */
export const ARCHIVE_RATIO = 1 / 500;

/** How the page says it, so the copy cannot drift from the number the maths uses. */
export const ARCHIVE_RATIO_LABEL = `1/${Math.round(1 / ARCHIVE_RATIO)}`;

export const policyOf = (settings: ArchivalSettings): Policy => ({
	archive: settings.archive_after_days,
	retain: settings.delete_after_days
});

export const settingsOf = (policy: Policy): ArchivalSettings => ({
	archive_after_days: policy.archive,
	delete_after_days: policy.retain
});

export const samePolicy = (a: Policy, b: Policy) =>
	a.archive === b.archive && a.retain === b.retain;

/**
 * The draft as the save bar posts it and the action reads it back: blank for
 * off. Both ends live here so the two cannot disagree about the encoding.
 */
export const toFields = (policy: Policy): Record<string, string> => ({
	archive: policy.archive === null ? '' : String(policy.archive),
	retain: policy.retain === null ? '' : String(policy.retain)
});

export function fromFields(form: FormData): Policy {
	const days = (name: string) => {
		const raw = String(form.get(name) ?? '').trim();
		return raw === '' ? null : Number(raw);
	};
	return { archive: days('archive'), retain: days('retain') };
}

/** The API's bounds, so the form refuses what the PUT would. */
export const LIMITS = { archive: 3650, retain: 7300 } as const;

export type Growth = 'bounded' | 'linear_efficient' | 'linear';

/** The same rule the backend uses for `growth_class`, applied to the draft. */
export const growthOf = (policy: Policy): Growth =>
	policy.retain !== null ? 'bounded' : policy.archive !== null ? 'linear_efficient' : 'linear';

/** Retention at or before archival deletes the rows before they can be archived. */
export const archivalEffective = (policy: Policy): boolean =>
	policy.archive !== null && (policy.retain === null || policy.retain > policy.archive);

export const liveBytes = (storage: StorageEstimate) =>
	storage.live_data_bytes + storage.live_index_bytes;

export const archiveBytes = (storage: StorageEstimate) =>
	storage.archive_data_bytes + storage.archive_index_bytes;

/**
 * Live size over the days it covers. A backfill stretches the span and so
 * lowers the rate, which is why this is labelled an estimate wherever it shows.
 */
export const dailyIngest = (storage: StorageEstimate): number =>
	storage.live_row_count === 0 ? 0 : liveBytes(storage) / Math.max(storage.live_data_span_days, 1);

/**
 * Day by day, one point a month. The stages are independent:
 * - archival only: live is capped at the archive window, the excess compressed;
 * - retention only: live is capped at the retention window, the excess gone;
 * - both, archive first: live capped as above, the archive capped at the gap;
 * - both, retention first: archival never happens, so it is retention only.
 *
 * Other tables are left out: nothing here changes them, and they would only
 * lift the whole curve.
 */
export function project(
	storage: StorageEstimate,
	policy: Policy
): { month: number; bytes: number }[] {
	const start = liveBytes(storage) + archiveBytes(storage);
	const months = Array.from({ length: PROJECTION_MONTHS + 1 }, (_, month) => month);

	if (storage.live_row_count === 0) return months.map((month) => ({ month, bytes: start }));

	const daily = dailyIngest(storage);
	const archiving = archivalEffective(policy);

	let live = liveBytes(storage);
	let archive = archiveBytes(storage);
	const points: { month: number; bytes: number }[] = [];

	for (let day = 0; day <= PROJECTION_MONTHS * DAYS_PER_MONTH; day++) {
		if (day % DAYS_PER_MONTH === 0) {
			points.push({ month: day / DAYS_PER_MONTH, bytes: Math.round(live + archive) });
		}

		live += daily;

		if (archiving) {
			const cap = policy.archive! * daily;
			if (live > cap) {
				archive += (live - cap) * ARCHIVE_RATIO;
				live = cap;
			}
			if (policy.retain !== null) {
				archive = Math.min(archive, (policy.retain - policy.archive!) * daily * ARCHIVE_RATIO);
			}
		} else if (policy.retain !== null) {
			live = Math.min(live, policy.retain * daily);
		}
	}

	return points;
}

/** What stops the draft being saved at all. */
export function invalid(policy: Policy): string | null {
	if (policy.archive !== null && !inRange(policy.archive, LIMITS.archive)) {
		return `Archive after must be a whole number of days, 1 to ${LIMITS.archive}.`;
	}
	if (policy.retain !== null && !inRange(policy.retain, LIMITS.retain)) {
		return `Delete after must be a whole number of days, 1 to ${LIMITS.retain}.`;
	}
	return null;
}

const inRange = (days: number, max: number) => isWholeIn(days, 1, max);

/** Saveable, but almost certainly not what was meant. */
export function conflict(policy: Policy): string | null {
	if (policy.archive === null || policy.retain === null || policy.retain > policy.archive)
		return null;
	return `Deletion at ${policy.retain} days comes before archival at ${policy.archive}, so rows are deleted before they can be archived — archival never happens with these numbers.`;
}
