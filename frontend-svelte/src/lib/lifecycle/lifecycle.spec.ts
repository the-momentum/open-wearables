import { describe, expect, it } from 'vitest';
import { formatBytes } from '$lib/utils/format';
import {
	ARCHIVE_RATIO_LABEL,
	archivalEffective,
	conflict,
	dailyIngest,
	fromFields,
	growthOf,
	invalid,
	policyOf,
	project,
	PROJECTION_MONTHS,
	samePolicy,
	settingsOf,
	toFields
} from './projection';
import type { StorageEstimate } from './types';

const MB = 1024 ** 2;

const storage = (over: Partial<StorageEstimate> = {}): StorageEstimate => ({
	live_data_bytes: 300 * MB,
	live_index_bytes: 100 * MB,
	archive_data_bytes: 2 * MB,
	archive_index_bytes: 1 * MB,
	other_tables_bytes: 50 * MB,
	total_bytes: 453 * MB,
	live_row_count: 1_000_000,
	archive_row_count: 4_000,
	live_data_span_days: 200,
	...over
});

/**
 * The old dashboard's `computeProjection`, copied as it was, so the port is
 * checked against what customers saw rather than against itself.
 */
function reference(
	archiveEnabled: boolean,
	archiveDays: number,
	deleteEnabled: boolean,
	deleteDays: number,
	liveTotalBytes: number,
	liveRows: number,
	archiveTotalBytes: number,
	liveDataSpanDays: number
) {
	if (liveRows === 0) {
		return Array.from({ length: 19 }, (_, m) => ({
			month: m,
			storage: liveTotalBytes + archiveTotalBytes
		}));
	}
	const archivalOn =
		archiveEnabled && archiveDays > 0 && (!deleteEnabled || deleteDays > archiveDays);
	const spanDays = Math.max(liveDataSpanDays, 1);
	const dailyRawBytes = liveTotalBytes / spanDays;
	const dailyArchiveBytes = dailyRawBytes * 0.002;
	let liveBytes = liveTotalBytes;
	let archiveBytes = archiveTotalBytes;
	const points: { month: number; storage: number }[] = [];
	for (let day = 0; day <= 18 * 30; day++) {
		if (day % 30 === 0) {
			points.push({ month: day / 30, storage: Math.round(liveBytes + archiveBytes) });
		}
		liveBytes += dailyRawBytes;
		if (archivalOn) {
			const liveCap = archiveDays * dailyRawBytes;
			if (liveBytes > liveCap) {
				const excess = liveBytes - liveCap;
				liveBytes = liveCap;
				archiveBytes += excess * 0.002;
			}
			if (deleteEnabled && deleteDays > archiveDays) {
				const archiveCap = (deleteDays - archiveDays) * dailyArchiveBytes;
				if (archiveBytes > archiveCap) archiveBytes = archiveCap;
			}
		} else if (deleteEnabled && deleteDays > 0) {
			const liveCap = deleteDays * dailyRawBytes;
			if (liveBytes > liveCap) liveBytes = liveCap;
		}
	}
	return points;
}

describe('project', () => {
	// Every combination the form can produce, against the old dashboard.
	const policies = [
		{ archive: null, retain: null },
		{ archive: 30, retain: null },
		{ archive: 400, retain: null },
		{ archive: null, retain: 90 },
		{ archive: 30, retain: 365 },
		{ archive: 90, retain: 30 },
		{ archive: 60, retain: 60 }
	];

	for (const policy of policies) {
		it(`matches the old dashboard for archive ${policy.archive}, retain ${policy.retain}`, () => {
			const s = storage();
			const old = reference(
				policy.archive !== null,
				policy.archive ?? 90,
				policy.retain !== null,
				policy.retain ?? 365,
				s.live_data_bytes + s.live_index_bytes,
				s.live_row_count,
				s.archive_data_bytes + s.archive_index_bytes,
				s.live_data_span_days
			);
			expect(project(s, policy).map((point) => point.bytes)).toEqual(
				old.map((point) => point.storage)
			);
		});
	}

	it('draws one point a month, today included', () => {
		const points = project(storage(), { archive: null, retain: null });
		expect(points).toHaveLength(PROJECTION_MONTHS + 1);
		expect(points[0]).toEqual({ month: 0, bytes: 403 * MB });
	});

	it('stays flat when there is nothing live to grow from', () => {
		const points = project(storage({ live_row_count: 0 }), { archive: null, retain: null });
		expect(new Set(points.map((point) => point.bytes)).size).toBe(1);
	});

	// The shape is the point of the chart: capped with retention, rising without.
	it('caps with retention and keeps growing without it', () => {
		const kept = project(storage(), { archive: null, retain: 30 });
		const forever = project(storage(), { archive: null, retain: null });
		expect(kept.at(-1)!.bytes).toBe(kept.at(-2)!.bytes);
		expect(forever.at(-1)!.bytes).toBeGreaterThan(forever.at(-2)!.bytes);
	});
});

describe('policy', () => {
	it('names the growth class the way the backend does', () => {
		expect(growthOf({ archive: null, retain: null })).toBe('linear');
		expect(growthOf({ archive: 90, retain: null })).toBe('linear_efficient');
		expect(growthOf({ archive: 90, retain: 365 })).toBe('bounded');
		expect(growthOf({ archive: null, retain: 365 })).toBe('bounded');
	});

	it('knows archival does nothing when deletion comes first', () => {
		expect(archivalEffective({ archive: 90, retain: 30 })).toBe(false);
		expect(archivalEffective({ archive: 90, retain: 90 })).toBe(false);
		expect(archivalEffective({ archive: 30, retain: 90 })).toBe(true);
		expect(conflict({ archive: 90, retain: 30 })).toMatch(/never happens/);
		expect(conflict({ archive: 30, retain: 90 })).toBeNull();
	});

	// The PUT rejects these with a 422 whose detail is a list, which the
	// reader would see as nothing — so the form says it first.
	it('refuses what the API would', () => {
		expect(invalid({ archive: 0, retain: null })).toMatch(/1 to 3650/);
		expect(invalid({ archive: 1.5, retain: null })).toMatch(/whole number/);
		expect(invalid({ archive: null, retain: 7301 })).toMatch(/1 to 7300/);
		expect(invalid({ archive: 90, retain: 365 })).toBeNull();
	});

	it('estimates the daily ingest off the span the live data covers', () => {
		expect(dailyIngest(storage())).toBe((400 * MB) / 200);
		expect(dailyIngest(storage({ live_row_count: 0 }))).toBe(0);
	});
});

describe('the policy on the wire', () => {
	// The save bar encodes, the action decodes: both halves live in one module,
	// and this is what holds them to each other.
	it('survives the trip through a form', () => {
		for (const policy of [
			{ archive: 30, retain: 365 },
			{ archive: null, retain: 90 },
			{ archive: null, retain: null }
		]) {
			const form = new FormData();
			for (const [name, value] of Object.entries(toFields(policy))) form.set(name, value);
			expect(fromFields(form)).toEqual(policy);
		}
	});

	it('maps onto the names the API uses, and back', () => {
		const policy = { archive: 30, retain: 365 };
		expect(settingsOf(policy)).toEqual({ archive_after_days: 30, delete_after_days: 365 });
		expect(policyOf(settingsOf(policy))).toEqual(policy);
	});

	it('tells a real change from none', () => {
		expect(samePolicy({ archive: 30, retain: null }, { archive: 30, retain: null })).toBe(true);
		expect(samePolicy({ archive: 30, retain: null }, { archive: 31, retain: null })).toBe(false);
	});

	it('says the ratio the maths uses', () => {
		expect(ARCHIVE_RATIO_LABEL).toBe('1/500');
	});
});

describe('formatBytes', () => {
	// Base 1024 and the backend's unit names, so the two never disagree.
	it('reads the way the API does', () => {
		expect(formatBytes(0)).toBe('0 B');
		expect(formatBytes(512)).toBe('512 B');
		expect(formatBytes(1536)).toBe('1.5 KB');
		expect(formatBytes(459 * MB)).toBe('459.0 MB');
		expect(formatBytes(3.2 * 1024 ** 3)).toBe('3.2 GB');
	});
});
