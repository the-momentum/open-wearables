import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { formatDuration, formatWindow, itemsLabel, statusTone } from './format';
import { overview, pageOf, runFilters, SYNC_STATUSES } from './runs';
import { SYNC_SOURCES, sourceLabel } from './source';
import type { SyncRunSummary, SyncStatus } from './types';

describe('statusTone', () => {
	it('maps a status the backend may add to neutral rather than crashing', () => {
		expect(statusTone('success')).toBe('success');
		expect(statusTone('something_new')).toBe('neutral');
	});
});

describe('formatWindow', () => {
	it('states one year once, and both when the span crosses a year', () => {
		expect(formatWindow('2026-08-05T00:00:00Z', '2026-09-04T00:00:00Z')).toBe(
			'5 Aug – 4 Sept 2026'
		);
		expect(formatWindow('2025-07-19T00:00:00Z', '2026-07-19T00:00:00Z')).toBe(
			'19 Jul 2025 – 19 Jul 2026'
		);
	});

	it('renders in UTC, so a midnight bound does not slip to the previous day', () => {
		expect(formatWindow('2026-01-01T00:00:00Z', '2026-01-02T00:00:00Z')).toBe('1 Jan – 2 Jan 2026');
	});

	it('is null when either bound is missing, since a half-open span says nothing', () => {
		expect(formatWindow(null, '2026-01-02T00:00:00Z')).toBeNull();
		expect(formatWindow('2026-01-01T00:00:00Z', null)).toBeNull();
	});
});

describe('formatDuration', () => {
	it('scales the unit to the length of the run', () => {
		expect(formatDuration('2026-01-01T00:00:00Z', '2026-01-01T00:00:00.400Z')).toBe('<1s');
		expect(formatDuration('2026-01-01T00:00:00Z', '2026-01-01T00:00:42Z')).toBe('42s');
		expect(formatDuration('2026-01-01T00:00:00Z', '2026-01-01T00:04:30Z')).toBe('4m 30s');
		expect(formatDuration('2026-01-01T00:00:00Z', '2026-01-01T02:05:00Z')).toBe('2h 5m');
	});

	it('is null for a run still going, and for an end before its start', () => {
		expect(formatDuration('2026-01-01T00:00:00Z', null)).toBeNull();
		expect(formatDuration('2026-01-01T02:00:00Z', '2026-01-01T01:00:00Z')).toBeNull();
	});
});

describe('sourceLabel', () => {
	it('names the sources a capitalised slug would mangle', () => {
		expect(sourceLabel('sdk')).toBe('SDK');
		expect(sourceLabel('xml_import')).toBe('XML import');
	});

	it('falls back for a source the backend adds later', () => {
		expect(sourceLabel('carrier_pigeon')).toBe('Carrier pigeon');
	});
});

describe('the filters match the API', () => {
	const schemas = (
		JSON.parse(readFileSync(resolve(process.cwd(), '../docs/openapi.json'), 'utf8')) as {
			components: { schemas: Record<string, { enum?: string[] }> };
		}
	).components.schemas;

	// A status or source the backend adds would otherwise be one nobody can filter by.
	it('offers every status and every source the backend has, and no others', () => {
		expect([...SYNC_STATUSES].sort()).toEqual([...(schemas.SyncStatus.enum ?? [])].sort());
		expect([...SYNC_SOURCES].sort()).toEqual([...(schemas.SyncSource.enum ?? [])].sort());
	});
});

describe('runFilters', () => {
	const read = (query: string) => runFilters(new URLSearchParams(query));

	it('keeps what the endpoint can match', () => {
		expect(read('user=0000000A-0000-4000-8000-000000000001&status=failed&source=sdk')).toEqual({
			user: '0000000a-0000-4000-8000-000000000001',
			provider: '',
			status: 'failed',
			source: 'sdk'
		});
	});

	// A partial id would be a 422, and an unknown status an empty list that reads as "nothing synced".
	it('drops a user that is not a UUID, and a status or source the API does not know', () => {
		expect(read('user=0000&status=exploded&source=fax')).toEqual({
			user: '',
			provider: '',
			status: '',
			source: ''
		});
	});
});

describe('pageOf', () => {
	const runs = Array.from({ length: 45 }, (_, index) => index);

	it('cuts the window into pages, the last one short', () => {
		expect(pageOf(runs, 2, 20)).toEqual({ page: 2, rows: runs.slice(20, 40) });
		expect(pageOf(runs, 3, 20).rows).toHaveLength(5);
	});

	// The window moves under a deep link: page nine of yesterday's list may not exist now.
	it('clamps a page past the end, or before the start', () => {
		expect(pageOf(runs, 9, 20).page).toBe(3);
		expect(pageOf(runs, 0, 20).page).toBe(1);
		expect(pageOf([], 4, 20)).toEqual({ page: 1, rows: [] });
	});
});

describe('overview', () => {
	const run = (status: SyncStatus, user = 'a') => ({ status, user_id: user }) as SyncRunSummary;

	it('adds up to the window, with a skipped sync counted as completed', () => {
		const counts = overview([
			run('success'),
			run('skipped', 'b'),
			run('skipped'),
			run('failed'),
			run('stale', 'c'),
			run('in_progress')
		]);
		expect(counts).toMatchObject({ running: 1, failed: 1, attention: 1, completed: 3, users: 3 });
		expect(counts.mix.map((part) => [part.key, part.value])).toEqual([
			['in_progress', 1],
			['success', 1],
			['failed', 1],
			['skipped', 2],
			['stale', 1]
		]);
	});
});

describe('itemsLabel', () => {
	it('shows how far along, or only the count when the total is unknown', () => {
		expect(itemsLabel({ items_processed: 40, items_total: 100 })).toBe('40/100');
		expect(itemsLabel({ items_processed: 40, items_total: null })).toBe('40');
		expect(itemsLabel({ items_processed: null, items_total: 100 })).toBeNull();
	});
});
