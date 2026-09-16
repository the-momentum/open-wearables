import { describe, expect, it } from 'vitest';
import { formatDuration, formatWindow, statusTone } from './format';
import { sourceLabel } from './source';

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
