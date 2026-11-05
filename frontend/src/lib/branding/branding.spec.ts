import { describe, expect, it } from 'vitest';
import { DEFAULT_BRANDING, pageTitle, parseBranding } from './branding';

const parse = (raw: string | undefined) => {
	const warnings: string[] = [];
	const branding = parseBranding(raw, (message) => warnings.push(message));
	return { branding, warnings };
};

describe('parseBranding', () => {
	it('uses the defaults silently when unset or blank', () => {
		expect(parse(undefined)).toEqual({ branding: DEFAULT_BRANDING, warnings: [] });
		expect(parse('  ')).toEqual({ branding: DEFAULT_BRANDING, warnings: [] });
	});

	it('applies every valid field', () => {
		const { branding, warnings } = parse(
			'{"name":" Acme (Staging) ","faviconUrl":"https://cdn.example.com/icon.png"}'
		);
		expect(branding).toEqual({
			name: 'Acme (Staging)',
			faviconUrl: 'https://cdn.example.com/icon.png'
		});
		expect(warnings).toEqual([]);
	});

	it('falls back to the defaults on invalid JSON or a non-object', () => {
		for (const raw of ['{name:', '"Acme"', '[]', 'null', '42']) {
			const { branding, warnings } = parse(raw);
			expect(branding).toEqual(DEFAULT_BRANDING);
			expect(warnings).toHaveLength(1);
		}
	});

	it('warns about unknown keys and ignores them', () => {
		const { branding, warnings } = parse('{"name":"Acme","favicon_url":"/x.png"}');
		expect(branding).toEqual({ name: 'Acme' });
		expect(warnings).toEqual([expect.stringContaining('"favicon_url"')]);
	});

	it('ignores an invalid name but keeps a valid favicon', () => {
		for (const name of ['""', '"   "', '42', 'null', JSON.stringify('x'.repeat(61))]) {
			const { branding, warnings } = parse(
				`{"name":${name},"faviconUrl":"https://cdn.example.com/ok.png"}`
			);
			expect(branding).toEqual({
				name: DEFAULT_BRANDING.name,
				faviconUrl: 'https://cdn.example.com/ok.png'
			});
			expect(warnings).toEqual([expect.stringContaining('"name"')]);
		}
	});

	it('ignores an unsafe or malformed favicon but keeps a valid name', () => {
		for (const url of [
			'"http://cdn.example.com/icon.png"',
			'"/favicon.png"',
			'"javascript:alert(1)"',
			'"data:image/png;base64,AAAA"',
			'"//evil.example/icon.png"',
			'"icon.png"',
			'"https://"',
			'true'
		]) {
			const { branding, warnings } = parse(`{"name":"Acme","faviconUrl":${url}}`);
			expect(branding).toEqual({ name: 'Acme' });
			expect(warnings).toEqual([expect.stringContaining('"faviconUrl"')]);
		}
	});
});

describe('pageTitle', () => {
	it('suffixes the page title with the brand name', () => {
		expect(pageTitle('Acme', 'Users')).toBe('Users · Acme');
		expect(pageTitle('Acme')).toBe('Acme');
	});
});
