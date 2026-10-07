import { page } from 'vitest/browser';
import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import ConnectionHeader from './ConnectionHeader.svelte';
import ConnectionRoutes from './ConnectionRoutes.svelte';
import type { Connection } from '$lib/connections/types';

const connection = (overrides: Partial<Connection> = {}): Connection =>
	({
		id: 'c1',
		provider: 'oura',
		status: 'active',
		scope: 'personal daily heartrate',
		last_synced_at: '2026-09-04T06:30:00Z',
		history_limit_days: null,
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

describe('ConnectionRoutes', () => {
	// An SDK connection carries no capability flags, so without the hint it read
	// as unconfigured and unsupported.
	it('shows an SDK connection as fed by the SDK, with nothing to start here', async () => {
		render(ConnectionRoutes, {
			connection: connection({
				provider: 'apple',
				rest_pull: false,
				webhook_ping: false,
				live_sync_mode: null
			}),
			viaSdk: true
		});

		await expect.element(page.getByText('Pushed by the SDK', { exact: true })).toBeVisible();
		await expect.element(page.getByText('Pushed by the SDK on demand')).toBeVisible();
		await expect.element(page.getByText('Not configured')).not.toBeInTheDocument();
		await expect
			.element(page.getByRole('button', { name: 'Sync history' }))
			.not.toBeInTheDocument();
	});
});
