import { env as privateEnv } from '$env/dynamic/private';
import { env as publicEnv } from '$env/dynamic/public';

const DEFAULT_API_URL = 'http://localhost:8000';

/**
 * Read at call time so one image can be pointed at any backend. API_URL is only
 * a shortcut for the server's own hop (http://app:8000 inside Docker); the
 * address everyone else uses is VITE_API_URL, which is what a deployment sets.
 */
function apiUrl(path: string): string {
	const base = privateEnv.API_URL || publicEnv.VITE_API_URL || DEFAULT_API_URL;
	return `${base.replace(/\/+$/, '')}${path}`;
}

export const API = {
	login: '/api/v1/auth/login',
	refresh: '/api/v1/token/refresh',
	revoke: '/api/v1/token/revoke',
	me: '/api/v1/auth/me'
} as const;

/** Mirrors backend `TokenResponse` (app/schemas/auth/token.py). */
export type TokenResponse = {
	access_token: string;
	token_type: string;
	refresh_token: string | null;
	expires_in: number | null;
};

export type Developer = {
	id: string;
	email: string;
	first_name: string | null;
	last_name: string | null;
	created_at: string;
};

export class ApiError extends Error {
	constructor(
		readonly status: number,
		message: string
	) {
		super(message);
		this.name = 'ApiError';
	}
}

async function raiseFor(response: Response): Promise<never> {
	let detail: string | undefined;
	try {
		const body = await response.json();
		detail = typeof body?.detail === 'string' ? body.detail : undefined;
	} catch {
		detail = undefined;
	}
	throw new ApiError(response.status, detail ?? response.statusText);
}

/** OAuth2 password flow: form-encoded, and the field is `username`. */
export async function login(email: string, password: string): Promise<TokenResponse> {
	const response = await fetch(apiUrl(API.login), {
		method: 'POST',
		headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
		body: new URLSearchParams({ username: email, password })
	});

	if (!response.ok) await raiseFor(response);
	return response.json();
}

export async function refreshTokens(refreshToken: string): Promise<TokenResponse> {
	const response = await fetch(apiUrl(API.refresh), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ refresh_token: refreshToken })
	});

	if (!response.ok) await raiseFor(response);
	return response.json();
}

/** Best effort: a logout must not fail because the token was already gone. */
export async function revokeToken(refreshToken: string): Promise<void> {
	try {
		await fetch(apiUrl(API.revoke), {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ refresh_token: refreshToken })
		});
	} catch {
		// Ending the local session is what matters.
	}
}

export async function apiGet<T>(path: string, accessToken: string): Promise<T> {
	const response = await fetch(apiUrl(path), {
		headers: { Authorization: `Bearer ${accessToken}` }
	});

	if (!response.ok) await raiseFor(response);
	return response.json();
}

async function apiWrite<T>(
	method: 'POST' | 'PATCH' | 'DELETE',
	path: string,
	accessToken: string,
	body?: unknown
): Promise<T> {
	const response = await fetch(apiUrl(path), {
		method,
		headers: {
			Authorization: `Bearer ${accessToken}`,
			...(body === undefined ? {} : { 'Content-Type': 'application/json' })
		},
		body: body === undefined ? undefined : JSON.stringify(body)
	});

	if (!response.ok) await raiseFor(response);
	return response.status === 204 ? (undefined as T) : response.json();
}

export const apiPost = <T>(path: string, accessToken: string, body?: unknown) =>
	apiWrite<T>('POST', path, accessToken, body);

export const apiPatch = <T>(path: string, accessToken: string, body: unknown) =>
	apiWrite<T>('PATCH', path, accessToken, body);

export const apiDelete = <T>(path: string, accessToken: string) =>
	apiWrite<T>('DELETE', path, accessToken);
