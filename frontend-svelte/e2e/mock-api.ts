/**
 * Stand-in for FastAPI so end-to-end tests walk the real sign-in path without
 * the full stack. Started by playwright.config.ts. Mirrors the contracts in
 * backend/app/api/routes/v1/{auth,token}.py.
 */
import { CREDENTIALS, DEVELOPER } from './fixtures';

const PORT = Number(process.env.MOCK_API_PORT ?? 8787);

let issued = 0;
const validAccessTokens = new Set<string>();
const validRefreshTokens = new Set<string>();

function issueTokens() {
	issued += 1;
	const access = `access-${issued}`;
	const refresh = `rt-${issued}`;
	validAccessTokens.add(access);
	validRefreshTokens.add(refresh);
	return { access_token: access, token_type: 'bearer', refresh_token: refresh, expires_in: 3600 };
}

const json = (body: unknown, status = 200) =>
	new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const server = Bun.serve({
	port: PORT,
	async fetch(request) {
		const { pathname } = new URL(request.url);

		if (pathname === '/api/v1/auth/login') {
			const form = await request.formData();
			const ok =
				form.get('username') === CREDENTIALS.email && form.get('password') === CREDENTIALS.password;
			return ok ? json(issueTokens()) : json({ detail: 'Incorrect email or password' }, 401);
		}

		if (pathname === '/api/v1/auth/me') {
			const token = request.headers.get('authorization')?.replace('Bearer ', '') ?? '';
			return validAccessTokens.has(token) ? json(DEVELOPER) : json({ detail: 'Unauthorized' }, 401);
		}

		if (pathname === '/api/v1/token/refresh') {
			const { refresh_token } = await request.json();
			if (!validRefreshTokens.has(refresh_token)) return json({ detail: 'Invalid' }, 401);
			// The real backend rotates: the old token stops working.
			validRefreshTokens.delete(refresh_token);
			return json(issueTokens());
		}

		if (pathname === '/api/v1/token/revoke') {
			const { refresh_token } = await request.json();
			validRefreshTokens.delete(refresh_token);
			return new Response(null, { status: 204 });
		}

		return json({ detail: 'Not found' }, 404);
	}
});

console.log(`mock api listening on ${server.url}`);
