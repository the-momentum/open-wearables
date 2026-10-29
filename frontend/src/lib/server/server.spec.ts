import { isRedirect, type Cookies } from '@sveltejs/kit';
import { getRequestEvent } from '$app/server';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiGet, apiPost, refreshTokens, type Developer, type TokenResponse } from './api';
import { createAuthContext, type AuthContext } from './auth';
import { forgetAll, keep, recall } from './cache';
import {
	decodeSession,
	encodeSession,
	needsRefresh,
	rotate,
	SESSION_COOKIE,
	sessionFromTokens,
	type Session
} from './session';

vi.mock('$app/server', () => ({ getRequestEvent: vi.fn() }));
vi.mock('./api', async (original) => ({
	...(await original<typeof import('./api')>()),
	refreshTokens: vi.fn(),
	revokeToken: vi.fn()
}));

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

	it('carries the prompt to change a default password, and nothing otherwise', () => {
		const prompted = sessionFromTokens(tokens({ password_change: 'required' }), DEVELOPER, NOW);
		expect(prompted.passwordChange).toBe('required');
		expect(sessionFromTokens(tokens(), DEVELOPER, NOW)).not.toHaveProperty('passwordChange');
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

/** Like SvelteKit's jar, a cookie set during a request is what the next get reads. */
function jar(stored: Session): Cookies {
	const values = new Map([[SESSION_COOKIE, encodeSession(stored)]]);
	return {
		get: (name: string) => values.get(name),
		set: (name: string, value: string) => void values.set(name, value),
		delete: (name: string) => void values.delete(name)
	} as unknown as Cookies;
}

const redirectOf = (work: Promise<unknown>) =>
	work.then(
		() => null,
		(thrown: unknown) => (isRedirect(thrown) ? thrown.location : thrown)
	);

describe('a token the API refuses', () => {
	afterEach(() => vi.mocked(refreshTokens).mockReset());

	// Refresh tokens differ per test: rotate() remembers a success for 30s.
	it('is renewed once for all the parallel calls of a request', async () => {
		vi.mocked(refreshTokens).mockResolvedValue(tokens({ access_token: 'renewed' }));
		const cookies = jar(session({ refreshToken: 'rt-parallel' }));
		const auth = createAuthContext(cookies);

		const answers = await Promise.all([auth.rejected('access'), auth.rejected('access')]);

		expect(answers).toEqual(['renewed', 'renewed']);
		expect(refreshTokens).toHaveBeenCalledTimes(1);
		expect(decodeSession(cookies.get(SESSION_COOKIE))?.accessToken).toBe('renewed');
		await expect(auth.accessToken()).resolves.toBe('renewed');
	});

	it('is not renewed when the session never held it, as during sign-in', async () => {
		const auth = createAuthContext(jar(session()));

		await expect(auth.rejected('from-a-sign-in')).resolves.toBeNull();
		expect(refreshTokens).not.toHaveBeenCalled();
	});

	it('ends the session when the refresh is refused too', async () => {
		vi.mocked(refreshTokens).mockRejectedValue(new Error('401'));
		const cookies = jar(session({ refreshToken: 'rt-refused' }));

		await expect(redirectOf(createAuthContext(cookies).rejected('access'))).resolves.toBe('/login');
		expect(cookies.get(SESSION_COOKIE)).toBeUndefined();
	});

	it('ends the session when the renewed token is refused as well', async () => {
		vi.mocked(refreshTokens).mockResolvedValue(tokens({ access_token: 'renewed' }));
		const auth = createAuthContext(jar(session({ refreshToken: 'rt-twice' })));
		await auth.rejected('access');

		await expect(redirectOf(auth.rejected('renewed'))).resolves.toBe('/login');
		expect(refreshTokens).toHaveBeenCalledTimes(1);
	});
});

describe('API calls with a refused token', () => {
	const rejected = vi.fn<AuthContext['rejected']>();
	const fetchMock = vi.fn<typeof fetch>();
	const reply = (status: number) => new Response('{}', { status });
	const sent = (call: number) => fetchMock.mock.calls[call][1];

	beforeEach(() => {
		vi.stubGlobal('fetch', fetchMock);
		vi.mocked(getRequestEvent).mockReturnValue({
			locals: { auth: { rejected } }
		} as unknown as ReturnType<typeof getRequestEvent>);
	});

	afterEach(() => {
		vi.unstubAllGlobals();
		fetchMock.mockReset();
		rejected.mockReset();
	});

	it('are sent again, body and all, with the renewed token', async () => {
		fetchMock.mockResolvedValueOnce(reply(401)).mockResolvedValueOnce(reply(200));
		rejected.mockResolvedValue('renewed');

		await apiPost('/api/v1/users', 'access', { email: 'a@example.com' });

		expect(sent(1)?.headers).toMatchObject({ Authorization: 'Bearer renewed' });
		expect(sent(1)?.body).toBe(sent(0)?.body);
	});

	it('fail as before when the token was not the session’s', async () => {
		fetchMock.mockResolvedValue(reply(401));
		rejected.mockResolvedValue(null);

		await expect(apiGet('/api/v1/auth/me', 'from-a-sign-in')).rejects.toMatchObject({
			status: 401
		});
		expect(fetchMock).toHaveBeenCalledTimes(1);
	});

	it('hand a refused retry back to the session, which ends it', async () => {
		fetchMock.mockResolvedValue(reply(401));
		rejected.mockResolvedValueOnce('renewed').mockRejectedValueOnce(new Error('signed out'));

		await expect(apiGet('/api/v1/users', 'access')).rejects.toThrow('signed out');
		expect(rejected).toHaveBeenLastCalledWith('renewed');
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
