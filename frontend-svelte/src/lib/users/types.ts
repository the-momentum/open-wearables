import type { Paginated } from '$lib/lists/types';

export type ConnectionStatus = 'active' | 'revoked' | 'expired';

export type UserConnection = {
	provider: string;
	status: ConnectionStatus;
	last_synced_at: string | null;
};

export type User = {
	id: string;
	created_at: string;
	first_name: string | null;
	last_name: string | null;
	email: string | null;
	/** Deprecated in the API but still writable, and customers rely on it. */
	external_user_id: string | null;
	last_synced_at: string | null;
	last_synced_provider: string | null;
	has_active_connection: boolean;
	/** Null means "not requested", [] means "none" — do not collapse the two. */
	connections: UserConnection[] | null;
};

export type PaginatedUsers = Paginated<User>;

/** Mirrors backend `UserDetailRead`: the list projection plus the tab-gating flag. */
export type UserDetail = User & {
	has_womens_health_data: boolean;
};
