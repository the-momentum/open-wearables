import { apiGet } from './api';

type AuthorizationUrl = { authorization_url: string; state: string };

export function authorizeProvider(provider: string, userId: string, redirectUri: string) {
	const params = new URLSearchParams({ user_id: userId, redirect_uri: redirectUri });
	return apiGet<AuthorizationUrl>(`/api/v1/oauth/${provider}/authorize?${params}`);
}
