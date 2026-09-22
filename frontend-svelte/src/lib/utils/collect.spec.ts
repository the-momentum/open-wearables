import { describe, expect, it } from 'vitest';
import { collect, grouped, toggled } from './collect';

describe('collect', () => {
	// Both orders are load-bearing: the groups come back in the order their first
	// item arrived, and the items inside keep the order they came in.
	it('keeps the order the items arrived in', () => {
		const groups = collect(['b1', 'a1', 'b2', 'a2'], (item) => item[0]);
		expect([...groups.keys()]).toEqual(['b', 'a']);
		expect(groups.get('b')).toEqual(['b1', 'b2']);
	});
});

describe('grouped', () => {
	it('hands the same grouping over as a list', () => {
		expect(grouped(['b1', 'a1', 'b2'], (item) => item[0])).toEqual([
			{ key: 'b', items: ['b1', 'b2'] },
			{ key: 'a', items: ['a1'] }
		]);
	});
});

describe('toggled', () => {
	it('adds what is missing and drops what is there', () => {
		expect(toggled(['a'], 'b')).toEqual(['a', 'b']);
		expect(toggled(['a', 'b'], 'a')).toEqual(['b']);
	});

	// The chips bind to it: mutating the array in place would not be seen.
	it('leaves the list it was given alone', () => {
		const list = ['a'];
		toggled(list, 'b');
		expect(list).toEqual(['a']);
	});
});
