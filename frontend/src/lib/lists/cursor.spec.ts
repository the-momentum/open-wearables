import { describe, expect, it } from 'vitest';
import { filterSearch } from './cursor';

const at = (query: string) => new URL(`http://localhost/users/u/workouts${query}`);

describe('filterSearch', () => {
	it('keeps the filters and drops where the list is and how long its pages are', () => {
		expect(filterSearch(at('?period=all&cursor=abc&at=3&size=20&provider=garmin&top=1'))).toBe(
			'?period=all&provider=garmin&top=1'
		);
	});

	it('is the same on every page of one list, so the totals are asked for once', () => {
		expect(filterSearch(at('?type=running&cursor=abc&at=2'))).toBe(
			filterSearch(at('?type=running'))
		);
	});

	it('is empty when only the position was set', () => {
		expect(filterSearch(at('?cursor=abc&at=2'))).toBe('');
	});

	it('drops the key a Svix list pages by', () => {
		expect(filterSearch(at('?iterator=xyz&status=failed'), 'iterator')).toBe('?status=failed');
	});
});
