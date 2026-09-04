import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';
import { playwright } from '@vitest/browser-playwright';
import adapter from '@sveltejs/adapter-node';
import { sveltekit } from '@sveltejs/kit/vite';
import { version } from './package.json' with { type: 'json' };

export default defineConfig({
	server: {
		host: '0.0.0.0',
		port: 3001,
		strictPort: true,
		// inotify does not fire reliably for files delivered by `docker compose
		// watch`, so fall back to polling inside the container only — polling on a
		// developer machine just burns CPU.
		watch: process.env.DOCKER ? { usePolling: true } : undefined
	},
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			adapter: adapter(),
			// Makes `version` from $app/environment the package version rather than
			// SvelteKit's default build timestamp, so the sidebar can show it.
			version: { name: version }
		})
	],
	test: {
		expect: { requireAssertions: true },
		projects: [
			{
				extends: './vite.config.ts',
				test: {
					name: 'client',
					browser: {
						enabled: true,
						provider: playwright(),
						instances: [{ browser: 'chromium', headless: true }]
					},
					// Named for the runner, not for a component: these files aggregate
					// a whole category, so `layout.browser.spec.ts` sits in
					// components/layout/ and covers every component in it.
					include: ['src/**/*.browser.spec.ts'],
					exclude: ['src/lib/server/**']
				}
			},

			{
				extends: './vite.config.ts',
				test: {
					name: 'server',
					environment: 'node',
					include: ['src/**/*.{test,spec}.{js,ts}'],
					exclude: ['src/**/*.browser.spec.ts']
				}
			}
		]
	}
});
