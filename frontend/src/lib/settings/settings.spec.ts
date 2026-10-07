import { describe, expect, it } from 'vitest';
import { outstanding, expired, inviteLink, invitationTone } from './invitations';
import { moved, ranked, reordered } from './priorities';
import { enabledMap, flipped } from './providers';
import type { Invitation, ProviderSetting } from './types';

const NOW = Date.parse('2026-09-23T12:00:00Z');

const invitation = (over: Partial<Invitation>): Invitation => ({
	id: 'i1',
	email: 'a@example.com',
	token: 'tok',
	status: 'sent',
	expires_at: '2026-09-30T12:00:00Z',
	created_at: '2026-09-20T12:00:00Z',
	...over
});

const setting = (over: Partial<ProviderSetting>): ProviderSetting => ({
	provider: 'oura',
	name: 'Oura',
	has_cloud_api: true,
	is_enabled: true,
	icon_url: '/static/oura.svg',
	live_sync_mode: 'pull',
	live_sync_configurable: true,
	...over
});

describe('moved', () => {
	it('swaps with the neighbour in the direction asked for', () => {
		expect(moved(['a', 'b', 'c'], 1, -1)).toEqual(['b', 'a', 'c']);
		expect(moved(['a', 'b', 'c'], 1, 1)).toEqual(['a', 'c', 'b']);
	});

	// The buttons are disabled at the ends, but a drag runs past them.
	it('leaves the list alone at either end', () => {
		const list = ['a', 'b'];
		expect(moved(list, 0, -1)).toBe(list);
		expect(moved(list, 1, 1)).toBe(list);
	});
});

describe('reordered', () => {
	const key = (item: string) => item;

	it('is false until something actually moves', () => {
		expect(reordered(['a', 'b'], ['a', 'b'], key)).toBe(false);
		expect(reordered(['b', 'a'], ['a', 'b'], key)).toBe(true);
	});
});

describe('ranked', () => {
	// Position is the priority: sending the index is what keeps the stored
	// number from drifting away from the order on screen.
	it('numbers from one, under the key the endpoint expects', () => {
		expect(
			ranked([{ provider: 'oura' }, { provider: 'garmin' }], 'provider', (e) => e.provider)
		).toEqual([
			{ provider: 'oura', priority: 1 },
			{ provider: 'garmin', priority: 2 }
		]);
	});
});

describe('provider settings', () => {
	const settings = [
		setting({}),
		setting({ provider: 'garmin', name: 'Garmin', is_enabled: false })
	];

	it('starts the draft from what the server holds', () => {
		expect(enabledMap(settings)).toEqual({ oura: true, garmin: false });
	});

	it('counts only what was actually flipped', () => {
		expect(flipped(settings, enabledMap(settings))).toEqual([]);
		expect(flipped(settings, { oura: false, garmin: false })).toHaveLength(1);
	});
});

describe('outstanding invitations', () => {
	// An accepted one is a team member and shows up in that list instead; a
	// lapsed one is noise. A failed send stays, because that one needs a human.
	it('keeps what is still worth acting on', () => {
		const rows = [
			invitation({ id: 'sent' }),
			invitation({ id: 'accepted', status: 'accepted' }),
			invitation({ id: 'lapsed', expires_at: '2026-09-01T12:00:00Z' }),
			invitation({ id: 'failed', status: 'failed', expires_at: '2026-09-01T12:00:00Z' })
		];

		expect(outstanding(rows, NOW).map((row) => row.id)).toEqual(['sent', 'failed']);
	});

	it('reads the expiry against now, not the day it was sent', () => {
		expect(expired(invitation({}), NOW)).toBe(false);
		expect(expired(invitation({ expires_at: '2026-09-22T12:00:00Z' }), NOW)).toBe(true);
	});

	it('gives a failed send a tone that is not success', () => {
		expect(invitationTone('sent')).toBe('success');
		expect(invitationTone('failed')).toBe('danger');
	});

	// The token is a credential, so it has to survive the query string intact.
	it('escapes the token into the link', () => {
		expect(inviteLink('https://app.example.com', 'a b+c')).toBe(
			'https://app.example.com/accept-invite?token=a%20b%2Bc'
		);
	});
});
