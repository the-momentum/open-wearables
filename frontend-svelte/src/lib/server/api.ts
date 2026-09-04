import { env } from '$env/dynamic/private';

const DEFAULT_API_URL = 'http://localhost:8000';

/** Read at call time so one image can be pointed at any backend. */
function apiUrl(path: string): string {
	return `${(env.API_URL || DEFAULT_API_URL).replace(/\/+$/, '')}${path}`;
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
