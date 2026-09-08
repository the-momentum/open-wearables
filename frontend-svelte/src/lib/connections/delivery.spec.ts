import { describe, expect, it } from 'vitest';
import {
	canForceLiveSync,
	canSyncHistory,
	historyDelivery,
	historyLimitNote,
	historyRanges,
	liveDelivery
} from './delivery';
import type { Connection } from './types';

const connection = (overrides: Partial<Connection>): Connection =>
	({
		rest_pull: false,
		webhook_stream: false,
		webhook_ping: false,
		webhook_callback: false,
		live_sync_mode: null,
		max_historical_days: null,
		...overrides
	}) as Connection;

describe('liveDelivery', () => {
	it('reads the configured mode first, and the transport only to explain it', () => {
		// Suunto: pushed whole payloads.
		expect(liveDelivery(connection({ live_sync_mode: 'webhook', webhook_stream: true }))).toBe(
			'Pushed by the provider'
		);
		// Oura in webhook mode: the ping/fetch split is deliberately flattened
		// into the same wording, because the provider is what triggers it.
		expect(
			liveDelivery(connection({ live_sync_mode: 'webhook', webhook_ping: true, rest_pull: true }))
		).toBe('Pushed by the provider');
		// Same provider, configured to pull instead.
		expect(liveDelivery(connection({ live_sync_mode: 'pull', webhook_ping: true }))).toBe(
			'Pulled on a schedule'
		);
	});

	it('says so when nothing is configured rather than implying a default', () => {
		expect(liveDelivery(connection({}))).toBe('Not configured');
	});
});

describe('historyDelivery', () => {
	it('mirrors the live wording, so the pair reads as one story', () => {
		expect(historyDelivery(connection({ rest_pull: true }))).toBe('Pulled on demand');
		expect(historyDelivery(connection({ webhook_callback: true }))).toBe(
			'Pushed by the provider on demand'
		);
		expect(historyDelivery(connection({}))).toBe('Not supported');
	});

	it('only notes a limit when the provider imposes one', () => {
		expect(historyLimitNote(connection({ max_historical_days: 30 }))).toContain('30 days');
		expect(historyLimitNote(connection({}))).toBeNull();
	});
});

describe('historyRanges', () => {
	it('lets the caller choose freely when no cap applies', () => {
		expect(historyRanges(connection({ rest_pull: true }))).toEqual([7, 30, 90, 180, 365]);
	});

	it('offers a capped pull provider everything up to and including the cap', () => {
		expect(historyRanges(connection({ rest_pull: true, max_historical_days: 30 }))).toEqual([
			7, 30
		]);
	});

	it('offers a callback backfill only its cap, because it ignores the window', () => {
		// Garmin: start_historical_sync drops `days` and always covers 30.
		expect(historyRanges(connection({ webhook_callback: true, max_historical_days: 30 }))).toEqual([
			30
		]);
	});
});

describe('what can be triggered', () => {
	it('offers a backfill whenever either route exists', () => {
		expect(canSyncHistory(connection({ rest_pull: true }))).toBe(true);
		expect(canSyncHistory(connection({ webhook_callback: true }))).toBe(true);
		expect(canSyncHistory(connection({}))).toBe(false);
	});

	it('hides Sync now on a webhook connection, which has nothing to pull', () => {
		expect(canForceLiveSync(connection({ rest_pull: true, live_sync_mode: 'pull' }))).toBe(true);
		expect(canForceLiveSync(connection({ rest_pull: true, live_sync_mode: 'webhook' }))).toBe(
			false
		);
		// Garmin has no REST path at all.
		expect(canForceLiveSync(connection({ webhook_stream: true, live_sync_mode: 'webhook' }))).toBe(
			false
		);
	});
});
