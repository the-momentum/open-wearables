import { afterEach, describe, expect, it, vi } from 'vitest';
import { refreshTokens, type Developer, type TokenResponse } from './api';
import { forgetAll, keep, recall } from './cache';
import {
	decodeSession,
	encodeSession,
	needsRefresh,
	rotate,
	sessionFromTokens,
	type Session
} from './session';

vi.mock('./api', () => ({ refreshTokens: vi.fn(), revokeToken: vi.fn() }));

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

describe('session cookie', () => {
	it('reads back what it wrote', () => {
		expect(decodeSession(encodeSession(session()))).toEqual(session());
	});

	it('treats a missing, mangled or foreign cookie as signed out', () => {
		expect(decodeSession(undefined)).toBeNull();
		expect(decodeSession('not-base64-json')).toBeNull();
		expect(decodeSession(Buffer.from('{"a":1}').toString('base64url'))).toBeNull();
	});
});

describe('rotate', () => {
	afterEach(() => vi.mocked(refreshTokens).mockReset());

	// The backend revokes a refresh token on first use: a second call with it
	// would 401 and sign the user out.
	it('spends one refresh token once, however many requests ask at the same time', async () => {
		vi.mocked(refreshTokens).mockResolvedValue(tokens({ refresh_token: 'rt-2' }));

		const [first, second] = await Promise.all([rotate('rt-shared'), rotate('rt-shared')]);
		const late = await rotate('rt-shared');

		expect(refreshTokens).toHaveBeenCalledTimes(1);
		expect([second.refresh_token, late.refresh_token]).toEqual([first.refresh_token, 'rt-2']);
	});

	it('tries again after a failed refresh rather than replaying the failure', async () => {
		vi.mocked(refreshTokens)
			.mockRejectedValueOnce(new Error('offline'))
			.mockResolvedValueOnce(tokens({ refresh_token: 'rt-3' }));

		await expect(rotate('rt-flaky')).rejects.toThrow('offline');
		expect((await rotate('rt-flaky')).refresh_token).toBe('rt-3');
	});
});

describe('cache', () => {
	afterEach(() => forgetAll());

	it('hands a value back until it expires, then forgets it', () => {
		keep('k', 42, 60, NOW);
		expect(recall('k', NOW + 59_000)).toBe(42);
		expect(recall('k', NOW + 60_000)).toBeNull();
	});
});
