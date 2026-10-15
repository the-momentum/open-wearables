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

/** https only: an http icon on an https portal is blocked as mixed content. */
const parseUrl = (value: unknown): string | undefined => {
	if (typeof value !== 'string') return undefined;
	const url = value.trim();
	if (url.length === 0 || url.length > URL_MAX_LENGTH) return undefined;
	try {
		return new URL(url).protocol === 'https:' ? url : undefined;
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
		warn('INSTANCE_BRANDING is not valid JSON; using the default branding.');
		return DEFAULT_BRANDING;
	}
	if (typeof value !== 'object' || value === null || Array.isArray(value)) {
		warn('INSTANCE_BRANDING must be a JSON object; using the default branding.');
		return DEFAULT_BRANDING;
	}

	const input = value as Record<string, unknown>;
	for (const key of Object.keys(input)) {
		if (!(KEYS as readonly string[]).includes(key)) {
			warn(`INSTANCE_BRANDING: unknown key "${key}" ignored. Supported: ${KEYS.join(', ')}.`);
		}
	}

	const branding: Branding = { ...DEFAULT_BRANDING };
	if ('name' in input) {
		const name = parseName(input.name);
		if (name) branding.name = name;
		else
			warn(
				`INSTANCE_BRANDING: "name" must be a string of 1-${NAME_MAX_LENGTH} characters; ignored.`
			);
	}
	if ('faviconUrl' in input) {
		const faviconUrl = parseUrl(input.faviconUrl);
		if (faviconUrl) branding.faviconUrl = faviconUrl;
		else warn('INSTANCE_BRANDING: "faviconUrl" must be an https:// URL; ignored.');
	}
	return branding;
}

/** "Users · Acme", or just "Acme" for a page without a title of its own. */
export const pageTitle = (name: string, title?: string) => (title ? `${title} · ${name}` : name);
