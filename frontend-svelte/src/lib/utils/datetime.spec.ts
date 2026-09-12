import { describe, expect, it } from 'vitest';
import { formatDate, formatRelativeTime } from './datetime';

const NOW = new Date('2026-09-05T12:00:00Z').getTime();
const ago = (ms: number) => new Date(NOW - ms).toISOString();

describe('formatRelativeTime', () => {
	// "Never" rather than a blank cell: a user who has never synced is a finding.
	it('says Never for a missing timestamp', () => {
		expect(formatRelativeTime(null, NOW)).toBe('Never');
	});

	it('says Never rather than crashing on a malformed timestamp', () => {
		expect(formatRelativeTime('not-a-date', NOW)).toBe('Never');
	});

	it.each([
		[30_000, 'Just now'],
		[5 * 60_000, '5 minutes ago'],
		[3 * 3_600_000, '3 hours ago'],
		[2 * 86_400_000, '2 days ago'],
		[400 * 86_400_000, 'last year']
	])('formats %i ms ago as %s', (elapsed, expected) => {
		expect(formatRelativeTime(ago(elapsed), NOW)).toBe(expected);
	});
});

describe('formatDate', () => {
	it('formats an absolute date', () => {
		expect(formatDate('2026-09-05T12:00:00Z')).toBe('5 Sept 2026');
	});

	it('falls back to a dash for missing or malformed input', () => {
		expect(formatDate(null)).toBe('—');
		expect(formatDate('nonsense')).toBe('—');
	});
});
