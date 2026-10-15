import { describe, expect, it } from 'vitest';
import { pairingLink, safeReturnUrl } from './links';

describe('pairingLink', () => {
	it('builds an absolute link an admin can paste into a message', () => {
		expect(pairingLink('https://app.example.com', 'abc-123')).toBe(
			'https://app.example.com/users/abc-123/pair'
		);
	});

	// origin from a proxy or config sometimes arrives with a trailing slash.
	it('does not double the slash', () => {
		expect(pairingLink('https://app.example.com/', 'abc-123')).toBe(
			'https://app.example.com/users/abc-123/pair'
		);
	});
});

describe('safeReturnUrl', () => {
	it('passes an ordinary web address through', () => {
		expect(safeReturnUrl('https://client.example.com/done')).toBe(
			'https://client.example.com/done'
		);
	});

	// The pairing link is public, so its query string is attacker-controlled.
	it.each(['javascript:alert(1)', 'data:text/html,<script>', 'not a url', ''])(
		'refuses %s',
		(raw) => {
			expect(safeReturnUrl(raw)).toBeNull();
		}
	);

	it('is null when the link carries none', () => {
		expect(safeReturnUrl(null)).toBeNull();
	});
});
