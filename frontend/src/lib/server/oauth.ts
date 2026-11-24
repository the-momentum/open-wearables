import { apiGet, apiPost } from './api';

type AuthorizationUrl = { authorization_url: string; state: string };
type ConnectToken = { token: string; expires_at: string; pair_url: string };

/** `connectToken` comes from the pairing link: the person opening it has no session. */
export function authorizeProvider(
	provider: string,
	userId: string,
	redirectUri: string,
	connectToken: string
) {
	const params = new URLSearchParams({ user_id: userId, redirect_uri: redirectUri });
	return apiGet<AuthorizationUrl>(`/api/v1/oauth/${provider}/authorize?${params}`, undefined, {
		'X-Open-Wearables-Connect-Token': connectToken
	});
}

export const mintConnectToken = (userId: string, accessToken: string) =>
	apiPost<ConnectToken>(`/api/v1/users/${userId}/connect-token`, accessToken);
