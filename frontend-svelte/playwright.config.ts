import { defineConfig } from '@playwright/test';

const MOCK_API_PORT = 8787;

export default defineConfig({
	testMatch: '**/*.e2e.{ts,js}',
	// Playwright infers this from a single webServer, but not from an array.
	use: { baseURL: 'http://localhost:4173' },
	webServer: [
		{
			command: 'bun e2e/mock-api.ts',
			port: MOCK_API_PORT,
			reuseExistingServer: !process.env.CI
		},
		{
			command: 'bun run build && bun run preview',
			port: 4173,
			env: {
				// Point the app at the stand-in backend rather than a real one, so
				// the suite exercises the true sign-in path without the full stack.
				API_URL: `http://localhost:${MOCK_API_PORT}`,
				// A throwaway database: sessions created here must not collide with
				// a developer's own.
				REDIS_URL: process.env.REDIS_URL ?? 'redis://localhost:6379/15'
			}
		}
	]
});
