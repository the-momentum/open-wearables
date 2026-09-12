import { apiDelete, apiGet, apiPost } from './api';
import type { Connection } from '$lib/connections/types';

export const fetchConnections = (userId: string, accessToken: string) =>
	apiGet<Connection[]>(`/api/v1/users/${userId}/connections`, accessToken);

const providerPath = (userId: string, provider: string) =>
	`/api/v1/users/${userId}/connections/${provider}`;

export const syncNow = (userId: string, provider: string, accessToken: string) =>
	apiPost(`/api/v1/providers/${provider}/users/${userId}/sync`, accessToken);

/** `days` is ignored by providers that enforce their own limit (Garmin: 30). */
export const syncHistory = (userId: string, provider: string, days: number, accessToken: string) =>
	apiPost(
		`/api/v1/providers/${provider}/users/${userId}/sync/historical?days=${days}`,
		accessToken
	);

/** Revokes the connection and clears its tokens; stored data stays. */
export const revokeConnection = (userId: string, provider: string, accessToken: string) =>
	apiDelete(providerPath(userId, provider), accessToken);

/** Deletes everything this provider ever delivered, then revokes. */
export const purgeConnectionData = (userId: string, provider: string, accessToken: string) =>
	apiDelete(`${providerPath(userId, provider)}/data`, accessToken);
