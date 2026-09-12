import { describe, expect, it } from 'vitest';
import { needsRefresh, sessionFromTokens, type Session } from './session';
import type { Developer, TokenResponse } from './api';

const DEVELOPER: Developer = {
	id: 'dev-1',
	email: 'dev@example.com',
	first_name: null,
	last_name: null,
	created_at: '2026-01-01T00:00:00Z'
};

const NOW = 1_700_000_000_000;

function tokens(overrides: Partial<TokenResponse> = {}): TokenResponse {
	return {
		access_token: 'access',
		token_type: 'bearer',
		refresh_token: 'rt-1',
		expires_in: 3600,
		...overrides
	};
}

function session(overrides: Partial<Session> = {}): Session {
	return { ...sessionFromTokens(tokens(), DEVELOPER, NOW), ...overrides };
}

describe('sessionFromTokens', () => {
	it('turns the relative expires_in into an absolute deadline', () => {
		expect(sessionFromTokens(tokens(), DEVELOPER, NOW).accessTokenExpiresAt).toBe(
			NOW + 3600 * 1000
		);
	});

	it('falls back to the backend default when expires_in is absent', () => {
		const built = sessionFromTokens(tokens({ expires_in: null }), DEVELOPER, NOW);
		expect(built.accessTokenExpiresAt).toBe(NOW + 3600 * 1000);
	});

	it('keeps the rotated refresh token, which the backend swaps on every refresh', () => {
		expect(sessionFromTokens(tokens({ refresh_token: 'rt-2' }), DEVELOPER, NOW).refreshToken).toBe(
			'rt-2'
		);
	});
});

describe('needsRefresh', () => {
	it('is false while the token has comfortable life left', () => {
		expect(needsRefresh(session(), NOW)).toBe(false);
	});

	it('is true once expired', () => {
		expect(needsRefresh(session(), NOW + 3601 * 1000)).toBe(true);
	});

	// The skew is the point: a token valid for another 30s would expire
	// mid-request without it.
	it('is true inside the safety margin, before actual expiry', () => {
		expect(needsRefresh(session(), NOW + (3600 - 30) * 1000)).toBe(true);
	});

	it('is false just outside the safety margin', () => {
		expect(needsRefresh(session(), NOW + (3600 - 90) * 1000)).toBe(false);
	});
});
