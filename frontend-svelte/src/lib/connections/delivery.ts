import type { Connection } from './types';

/**
 * A provider with no cloud API (Apple Health, Samsung Health, Health Connect)
 * is fed by the mobile SDK: the app does both jobs, and nothing on this side
 * configures or starts either.
 */
export const SDK_DELIVERY = {
	live: {
		label: 'Pushed by the SDK',
		hint: 'The SDK uploads in the background whenever the phone lets it: on new Health data on iOS, about every 15 minutes on Android.'
	},
	history: {
		label: 'Pushed by the SDK on demand',
		hint: "The app starts it through the SDK, at any time, as far back as its syncDaysBack setting. It can't be started from this dashboard."
	}
};

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
 * A callback backfill ignores the requested window - Garmin's
 * start_historical_sync drops `days` and always covers its cap - so only the cap
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
