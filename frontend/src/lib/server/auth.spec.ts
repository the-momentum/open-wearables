import { isRedirect, type Cookies } from '@sveltejs/kit';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
	apiGet,
	apiPost,
	ApiError,
	refreshTokens,
	type Developer,
	type TokenResponse
} from './api';
import { createAuthContext, type AuthContext } from './auth';
import { decodeSession, encodeSession, SESSION_COOKIE, sessionFromTokens } from './session';

vi.mock('$app/server', () => ({ getRequestEvent: vi.fn() }));
vi.mock('./api', async (original) => ({
	...(await original<typeof import('./api')>()),
	refreshTokens: vi.fn()
}));

const { getRequestEvent } = await import('$app/server');

const DEVELOPER: Developer = {
	id: 'dev-1',
	email: 'dev@example.com',
	first_name: null,
	last_name: null,
	created_at: '2026-01-01T00:00:00Z'
};

function tokens(access: string, refresh: string | null): TokenResponse {
	return { access_token: access, token_type: 'bearer', refresh_token: refresh, expires_in: 3600 };
}

/** Enough of SvelteKit's cookie jar: a set is visible to the next get, as in a request. */
function jar(access: string, refresh: string | null = `rt-of-${access}`): Cookies {
	const values = new Map([
		[SESSION_COOKIE, encodeSession(sessionFromTokens(tokens(access, refresh), DEVELOPER))]
	]);
	return {
		get: (name: string) => values.get(name),
		set: (name: string, value: string) => void values.set(name, value),
		delete: (name: string) => void values.delete(name)
	} as unknown as Cookies;
}

const stored = (cookies: Cookies) => decodeSession(cookies.get(SESSION_COOKIE));

async function redirectOf(work: Promise<unknown>): Promise<string> {
	const thrown = await work.then(
		() => null,
		(error: unknown) => error
	);
	if (!isRedirect(thrown)) throw new Error(`expected a redirect, got ${String(thrown)}`);
	return thrown.location;
}

describe('AuthContext.rejected', () => {
	afterEach(() => vi.mocked(refreshTokens).mockReset());

	it('leaves a token the session does not hold to its caller', async () => {
		const auth = createAuthContext(jar('access-held'));

		await expect(auth.rejected('access-from-a-sign-in')).resolves.toBeNull();
		expect(refreshTokens).not.toHaveBeenCalled();
	});

	it('renews a refused token and keeps the renewed session', async () => {
		vi.mocked(refreshTokens).mockResolvedValue(tokens('access-new', 'rt-new'));
		const cookies = jar('access-refused-1');
		const auth = createAuthContext(cookies);

		await expect(auth.rejected('access-refused-1')).resolves.toBe('access-new');
		expect(stored(cookies)?.accessToken).toBe('access-new');
		// Later calls in the same request use the renewed token straight away.
		await expect(auth.accessToken()).resolves.toBe('access-new');
	});

	it('renews once for all the parallel calls a page makes', async () => {
		vi.mocked(refreshTokens).mockResolvedValue(tokens('access-new', 'rt-new'));
		const auth = createAuthContext(jar('access-refused-2'));

		const answers = await Promise.all([
			auth.rejected('access-refused-2'),
			auth.rejected('access-refused-2')
		]);

		expect(answers).toEqual(['access-new', 'access-new']);
		expect(refreshTokens).toHaveBeenCalledTimes(1);
	});

	// A database or SECRET_KEY the session never belonged to: once used to answer with a 500.
	it('clears the session and sends to sign-in when the refresh is refused too', async () => {
		vi.mocked(refreshTokens).mockRejectedValue(new ApiError(401, 'Invalid refresh token'));
		const cookies = jar('access-refused-3');

		await expect(redirectOf(createAuthContext(cookies).rejected('access-refused-3'))).resolves.toBe(
			'/login'
		);
		expect(cookies.get(SESSION_COOKIE)).toBeUndefined();
	});

	it('clears a session that has no refresh token to try', async () => {
		const cookies = jar('access-refused-4', null);

		await expect(redirectOf(createAuthContext(cookies).rejected('access-refused-4'))).resolves.toBe(
			'/login'
		);
		expect(cookies.get(SESSION_COOKIE)).toBeUndefined();
		expect(refreshTokens).not.toHaveBeenCalled();
	});

	it('gives up when the renewed token is refused as well', async () => {
		vi.mocked(refreshTokens).mockResolvedValue(tokens('access-new', 'rt-new'));
		const auth = createAuthContext(jar('access-refused-5'));
		await auth.rejected('access-refused-5');

		await expect(redirectOf(auth.rejected('access-new'))).resolves.toBe('/login');
		expect(refreshTokens).toHaveBeenCalledTimes(1);
	});
});

describe('API calls with a refused token', () => {
	const rejected = vi.fn<AuthContext['rejected']>();
	const fetchMock = vi.fn<typeof fetch>();

	const reply = (status: number, body: unknown = {}) =>
		new Response(JSON.stringify(body), { status });
	const bearer = (call: number) =>
		(fetchMock.mock.calls[call][1]?.headers as Record<string, string>).Authorization;

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

	it('retries once with the renewed token', async () => {
		fetchMock.mockResolvedValueOnce(reply(401)).mockResolvedValueOnce(reply(200, { ok: true }));
		rejected.mockResolvedValue('access-new');

		await expect(apiGet('/api/v1/users', 'access-old')).resolves.toEqual({ ok: true });
		expect(rejected).toHaveBeenCalledWith('access-old');
		expect([bearer(0), bearer(1)]).toEqual(['Bearer access-old', 'Bearer access-new']);
	});

	it('sends the same body again on the retry', async () => {
		fetchMock.mockResolvedValueOnce(reply(401)).mockResolvedValueOnce(reply(200, {}));
		rejected.mockResolvedValue('access-new');

		await apiPost('/api/v1/users', 'access-old', { email: 'a@example.com' });

		expect(fetchMock.mock.calls[1][1]?.body).toBe(JSON.stringify({ email: 'a@example.com' }));
		expect(fetchMock.mock.calls[1][1]?.method).toBe('POST');
	});

	it('reports the refusal when the token was not the session’s', async () => {
		fetchMock.mockResolvedValue(reply(401, { detail: 'Could not validate credentials' }));
		rejected.mockResolvedValue(null);

		await expect(apiGet('/api/v1/auth/me', 'access-other')).rejects.toMatchObject({ status: 401 });
		expect(fetchMock).toHaveBeenCalledTimes(1);
	});

	it('hands a refused retry back to the session to end it', async () => {
		fetchMock.mockResolvedValue(reply(401));
		rejected.mockResolvedValueOnce('access-new').mockRejectedValueOnce(new Error('signed out'));

		await expect(apiGet('/api/v1/users', 'access-old')).rejects.toThrow('signed out');
		expect(rejected).toHaveBeenLastCalledWith('access-new');
	});

	it('leaves other failures and tokenless calls alone', async () => {
		fetchMock.mockResolvedValueOnce(reply(403)).mockResolvedValueOnce(reply(401));

		await expect(apiGet('/api/v1/users', 'access-old')).rejects.toMatchObject({ status: 403 });
		await expect(apiGet('/api/v1/public')).rejects.toMatchObject({ status: 401 });
		expect(rejected).not.toHaveBeenCalled();
	});
});
