import { describe, expect, it } from 'vitest';
import { AVATAR_TONES, avatarTone, fullName, initials } from './avatar';

const user = (
	over: Partial<{ first_name: string | null; last_name: string | null; email: string | null }>
) => ({
	first_name: null,
	last_name: null,
	email: null,
	...over
});

describe('initials', () => {
	it.each([
		[{ first_name: 'Zofia', last_name: 'Kowalska' }, 'ZK'],
		[{ first_name: 'Zofia' }, 'Z'],
		[{ last_name: 'Kowalska' }, 'K'],
		[{ email: 'ola@example.com' }, 'OL'],
		[{}, '—']
	])('renders %o as %s', (over, expected) => {
		expect(initials(user(over))).toBe(expected);
	});

	// Seed data arrives with stray whitespace often enough to matter.
	it('ignores names that are only whitespace', () => {
		expect(initials(user({ first_name: '   ', email: 'ola@example.com' }))).toBe('OL');
	});
});

describe('avatarTone', () => {
	it('is stable for the same id', () => {
		expect(avatarTone('abc')).toBe(avatarTone('abc'));
	});

	it('only ever returns a token-based tone', () => {
		for (const id of ['a', 'abc', '00000000-0000-4000-8000-000000000007', '']) {
			expect(AVATAR_TONES).toContain(avatarTone(id));
		}
	});

	// A single tone for every row would defeat the point.
	it('spreads ids across more than one tone', () => {
		const seen = new Set(Array.from({ length: 50 }, (_, index) => avatarTone(`user-${index}`)));
		expect(seen.size).toBeGreaterThan(2);
	});
});

describe('fullName', () => {
	it('joins what is present and is empty when nothing is', () => {
		expect(fullName({ first_name: 'Zofia', last_name: 'Kowalska' })).toBe('Zofia Kowalska');
		expect(fullName({ first_name: null, last_name: 'Kowalska' })).toBe('Kowalska');
		expect(fullName({ first_name: null, last_name: null })).toBe('');
	});
});
