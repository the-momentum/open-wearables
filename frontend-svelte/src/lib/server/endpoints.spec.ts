import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * Every API path the server layer calls, as written in the source. The mock in
 * `e2e/` answers whatever this asks for, so a wrong path passes every test in
 * the suite and only fails against the real backend — which is how
 * `/api/v1/stats` shipped when the route is mounted at `/api/v1/dashboard/stats`.
 */
const CALLED = /['"`](\/api\/v1\/[^'"`?]*)/g;

const placeholders = (path: string) =>
	path.replace(/\$\{[^}]*\}/g, '{x}').replace(/\{[^}]*\}/g, '{x}');

function calledPaths(): { file: string; path: string }[] {
	const dir = resolve(process.cwd(), 'src/lib/server');

	return readdirSync(dir)
		.filter((file) => file.endsWith('.ts') && !file.endsWith('.spec.ts'))
		.flatMap((file) => {
			const source = readFileSync(resolve(dir, file), 'utf8');
			return [...source.matchAll(CALLED)].map((match) => ({
				file,
				path: placeholders(match[1]).replace(/\/$/, '')
			}));
		});
}

function specPaths(): Set<string> {
	const spec = JSON.parse(readFileSync(resolve(process.cwd(), '../docs/openapi.json'), 'utf8')) as {
		paths: Record<string, unknown>;
	};

	return new Set(Object.keys(spec.paths).map((path) => placeholders(path).replace(/\/$/, '')));
}

describe('the endpoints this frontend calls', () => {
	// A router's decorator says `/stats`; the prefix it is mounted under says the
	// rest. Reading one without the other is the mistake this guards.
	it('all exist in the generated OpenAPI spec', () => {
		const known = specPaths();
		const missing = calledPaths().filter((called) => !known.has(called.path));

		expect(missing).toEqual([]);
	});

	it('found something to check, so a silent zero cannot pass', () => {
		expect(calledPaths().length).toBeGreaterThan(20);
	});
});
