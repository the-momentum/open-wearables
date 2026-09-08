import type { Connection } from './types';

/** Configured mode first; the capability flags only explain how it travels. */
export function liveDelivery(connection: Connection): string {
	if (!connection.live_sync_mode) return 'Not configured';
	if (connection.live_sync_mode === 'pull') return 'Pulled on a schedule';
	// One string for both webhook shapes, flattening a real difference:
	// webhook_ping only notifies and the data still comes over REST.
	if (connection.webhook_stream || connection.webhook_ping) return 'Pushed by the provider';
	return 'Webhook';
}

export function historyDelivery(connection: Connection): string {
	if (connection.webhook_callback) return 'Pushed by the provider on demand';
	if (connection.rest_pull) return 'Pulled on demand';
	return 'Not supported';
}

export const canSyncHistory = (connection: Connection) =>
	connection.webhook_callback || connection.rest_pull;

/** A webhook connection has nothing to pull: the provider decides when to send. */
export const canForceLiveSync = (connection: Connection) =>
	connection.rest_pull && connection.live_sync_mode !== 'webhook';

const RANGES = [7, 30, 90, 180, 365] as const;

export const DEFAULT_RANGE = 90;

/**
 * A callback backfill ignores the requested window — Garmin's
 * start_historical_sync drops `days` and always covers its cap — so only the cap
 * is truthful there. Deleting that branch is the whole fix if it ever changes.
 */
export function historyRanges(connection: Connection): number[] {
	const cap = connection.max_historical_days;
	if (cap === null) return [...RANGES];
	if (connection.webhook_callback) return [cap];
	return [...RANGES.filter((days) => days < cap), cap];
}

export const historyLimitNote = (connection: Connection): string | null =>
	connection.max_historical_days
		? `The provider allows at most ${connection.max_historical_days} days of history.`
		: null;
