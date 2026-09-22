import { describe, expect, it } from 'vitest';
import { groupEvents, namesIn } from './events';
import { hasContent, statusOf, triggerOf } from './status';
import type { EventType } from './types';

const types: EventType[] = [
	{ name: 'connection.created', description: '', child_events: null },
	{ name: 'connection.revoked', description: '', child_events: null },
	{ name: 'sync.completed', description: '', child_events: null },
	{ name: 'workout.created', description: '', child_events: null },
	{
		name: 'heart_rate.created',
		description: '',
		child_events: ['series.heart_rate', 'series.resting_heart_rate']
	},
	{ name: 'series.heart_rate', description: '', child_events: null },
	{ name: 'series.resting_heart_rate', description: '', child_events: null }
];

describe('groupEvents', () => {
	// Eighty names arrive in one flat list; the families are the word before the
	// dot, and the series groups declare their own children.
	it('folds the loose events into families by their prefix', () => {
		const families = groupEvents(types).filter((group) => group.parent === null);
		expect(families.map((group) => group.label)).toEqual(['Connection', 'Sync', 'Workout']);
		expect(families[0].events).toHaveLength(2);
	});

	it('keeps a series group with its children under it', () => {
		const series = groupEvents(types).find((group) => group.parent !== null);
		expect(series?.label).toBe('Heart rate');
		expect(series?.events.map((event) => event.name)).toEqual([
			'series.heart_rate',
			'series.resting_heart_rate'
		]);
	});

	// A child already sits under its group, so listing it again as a family of
	// its own would offer the same event twice.
	it('does not list a child event loose as well', () => {
		const loose = groupEvents(types)
			.filter((group) => group.parent === null)
			.flatMap((group) => group.events.map((event) => event.name));
		expect(loose).not.toContain('series.heart_rate');
	});

	it('drops a child the list never declared', () => {
		const orphan = [{ name: 'a.created', description: '', child_events: ['series.ghost'] }];
		expect(groupEvents(orphan)[0].events).toEqual([]);
	});

	it('counts the group event itself among what a family can send', () => {
		const series = groupEvents(types).find((group) => group.parent !== null)!;
		expect(namesIn(series)).toEqual([
			'heart_rate.created',
			'series.heart_rate',
			'series.resting_heart_rate'
		]);
	});
});

describe('hasContent', () => {
	/**
	 * Svix 2.x keeps the response body and the event payload behind a
	 * `with_content` flag that defaults to false, so both arrive empty until the
	 * backend asks. "Nobody asked" must not read as "the provider sent nothing".
	 */
	it('treats an empty object and an empty string as nothing to show', () => {
		expect(hasContent({})).toBe(false);
		expect(hasContent('')).toBe(false);
		expect(hasContent('   ')).toBe(false);
		expect(hasContent(null)).toBe(false);
	});

	it('shows anything that actually arrived', () => {
		expect(hasContent({ event: 'workout.created' })).toBe(true);
		expect(hasContent('{"ok":true}')).toBe(true);
	});
});

describe('statusOf', () => {
	it('names the four statuses Svix uses', () => {
		expect(statusOf(0).label).toBe('Delivered');
		expect(statusOf(2)).toEqual({ label: 'Failed', tone: 'danger' });
	});

	// A status this build has never seen still has to render as something.
	it('falls back on a status it does not know', () => {
		expect(statusOf(9).label).toBe('Status 9');
	});

	it('tells a retry from a scheduled send', () => {
		expect([triggerOf(0), triggerOf(1)]).toEqual(['Scheduled', 'Retry']);
	});
});
