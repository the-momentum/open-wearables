import { page } from 'vitest/browser';
import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import ConnectionHeader from './ConnectionHeader.svelte';
import type { Connection } from '$lib/connections/types';

const connection = (overrides: Partial<Connection> = {}): Connection =>
	({
		id: 'c1',
		provider: 'oura',
		status: 'active',
		scope: 'personal daily heartrate',
		last_synced_at: '2026-09-04T06:30:00Z',
		max_historical_days: null,
		rest_pull: true,
		webhook_stream: false,
		webhook_ping: true,
		webhook_callback: false,
		live_sync_mode: 'pull',
		linked_user_ids: [],
		...overrides
	}) as Connection;

const noop = () => {};

describe('ConnectionHeader', () => {
	it('puts the scope count behind a control, so the list costs no height', async () => {
		render(ConnectionHeader, {
			connection: connection(),
			label: 'Oura',
			onrevoke: noop,
			onpurge: noop
		});

		await expect.element(page.getByRole('button', { name: '3 granted scopes' })).toBeVisible();
	});

	it('offers no badge at all when the provider reported no scope', async () => {
		render(ConnectionHeader, {
			connection: connection({ scope: null }),
			label: 'Suunto',
			onrevoke: noop,
			onpurge: noop
		});

		await expect
			.element(page.getByRole('button', { name: /granted scopes/ }))
			.not.toBeInTheDocument();
	});
});
