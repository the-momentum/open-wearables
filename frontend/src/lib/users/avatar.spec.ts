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
		[{}, '-']
	])('renders %o as %s', (over, expected) => {
		expect(initials(user(over))).toBe(expected);
	});

	// Seed data arrives with stray whitespace often enough to matter.
	it('ignores names that are only whitespace', () => {
		expect(initials(user({ first_name: '   ', email: 'ola@example.com' }))).toBe('OL');
	});
});

describe('fullName', () => {
	it('joins what is present and is empty when nothing is', () => {
		expect(fullName({ first_name: 'Zofia', last_name: 'Kowalska' })).toBe('Zofia Kowalska');
		expect(fullName({ first_name: null, last_name: 'Kowalska' })).toBe('Kowalska');
		expect(fullName({ first_name: null, last_name: null })).toBe('');
	});
});

describe('avatarTone', () => {
	const ids = Array.from(
		{ length: 20 },
		(_, n) => `00000000-0000-4000-8000-${String(n + 1).padStart(12, '0')}`
	);

	it('gives a key the same tone every time', () => {
		expect(avatarTone(ids[0])).toBe(avatarTone(ids[0]));
	});

	// Seeded ids differ only in their last digits; a sum of char codes would
	// put whole runs of them on one colour.
	it('spreads keys that differ by one digit across every tone', () => {
		expect(new Set(ids.map(avatarTone))).toEqual(new Set(AVATAR_TONES));
	});
});
