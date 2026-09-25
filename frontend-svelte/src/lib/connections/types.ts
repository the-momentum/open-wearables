/**
 * The fields this app reads from backend `UserConnectionWithCapabilities`.
 * Deliberately not the whole schema — see AGENTS.md on porting types.
 */
export type Connection = {
	id: string;
	provider: string;
	status: 'active' | 'revoked' | 'expired';
	scope: string | null;
	last_synced_at: string | null;
	max_historical_days: number | null;
	rest_pull: boolean;
	webhook_stream: boolean;
	webhook_ping: boolean;
	webhook_callback: boolean;
	live_sync_mode: string | null;
	linked_user_ids: string[];
};
