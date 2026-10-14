/**
 * Deployment branding, from the VITE_BRANDING environment variable: one JSON
 * object, so a new option never needs a new variable.
 *
 *   VITE_BRANDING='{"name":"Acme Wearables (Staging)","faviconUrl":"/favicon-staging.png"}'
 *
 * Branding is cosmetic, so a bad value never stops the portal: whatever fails
 * validation is reported through `warn` and left at its default.
 */
export type Branding = {
	/** Replaces "Open Wearables" in page titles. */
	name: string;
	/** Replaces the bundled favicons when set. */
	faviconUrl?: string;
};

export const DEFAULT_BRANDING: Branding = { name: 'Open Wearables' };

const NAME_MAX_LENGTH = 60;
const URL_MAX_LENGTH = 2048;
const KEYS = ['name', 'faviconUrl'] as const;

const parseName = (value: unknown): string | undefined => {
	if (typeof value !== 'string') return undefined;
	const name = value.trim();
	return name.length > 0 && name.length <= NAME_MAX_LENGTH ? name : undefined;
};

/** An absolute http(s) URL, or a path on this origin ("/x", not "//host/x"). */
const parseUrl = (value: unknown): string | undefined => {
	if (typeof value !== 'string') return undefined;
	const url = value.trim();
	if (url.length === 0 || url.length > URL_MAX_LENGTH) return undefined;
	if (url.startsWith('/')) return url.startsWith('//') ? undefined : url;
	try {
		const { protocol } = new URL(url);
		return protocol === 'https:' || protocol === 'http:' ? url : undefined;
	} catch {
		return undefined;
	}
};

export function parseBranding(
	raw: string | undefined,
	warn: (message: string) => void = () => {}
): Branding {
	if (raw === undefined || raw.trim() === '') return DEFAULT_BRANDING;

	let value: unknown;
	try {
		value = JSON.parse(raw);
	} catch {
		warn('VITE_BRANDING is not valid JSON; using the default branding.');
		return DEFAULT_BRANDING;
	}
	if (typeof value !== 'object' || value === null || Array.isArray(value)) {
		warn('VITE_BRANDING must be a JSON object; using the default branding.');
		return DEFAULT_BRANDING;
	}

	const input = value as Record<string, unknown>;
	for (const key of Object.keys(input)) {
		if (!(KEYS as readonly string[]).includes(key)) {
			warn(`VITE_BRANDING: unknown key "${key}" ignored. Supported: ${KEYS.join(', ')}.`);
		}
	}

	const branding: Branding = { ...DEFAULT_BRANDING };
	if ('name' in input) {
		const name = parseName(input.name);
		if (name) branding.name = name;
		else
			warn(`VITE_BRANDING: "name" must be a string of 1-${NAME_MAX_LENGTH} characters; ignored.`);
	}
	if ('faviconUrl' in input) {
		const faviconUrl = parseUrl(input.faviconUrl);
		if (faviconUrl) branding.faviconUrl = faviconUrl;
		else
			warn(
				'VITE_BRANDING: "faviconUrl" must be an http(s) URL or a path starting with "/"; ignored.'
			);
	}
	return branding;
}

/** "Users · Acme", or just "Acme" for a page without a title of its own. */
export const pageTitle = (name: string, title?: string) => (title ? `${title} · ${name}` : name);
