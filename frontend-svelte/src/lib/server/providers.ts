import { apiGet } from './api';
import { redis } from './redis';

export type Provider = {
	provider: string;
	name: string;
	has_cloud_api: boolean;
	is_enabled: boolean;
	/** Relative to the API base, which the browser cannot reach under cookie sessions. */
	icon_url: string;
};

const TTL_SECONDS = 60;

/** Fails open, unlike the session store: no Redis costs a call, not a login. */
async function cached(key: string, load: () => Promise<Provider[]>): Promise<Provider[]> {
	try {
		const hit = await redis().get(key);
		if (hit) return byName(JSON.parse(hit) as Provider[]);
	} catch {
		// Fall through to the API.
	}

	const providers = await load();
	redis()
		.set(key, JSON.stringify(providers), 'EX', TTL_SECONDS)
		.catch(() => {});
	return byName(providers);
}

/** The API orders them by when they were added to its enum, which says nothing. */
const byName = (providers: Provider[]) =>
	[...providers].sort((a, b) => a.name.localeCompare(b.name));

/** Enabled only: a filter chip for a provider nobody can connect is noise. */
export const fetchProviders = (accessToken: string) =>
	cached('ow:providers:enabled', () =>
		apiGet<Provider[]>('/api/v1/oauth/providers?enabled_only=true', accessToken)
	);

/** Public: the pairing page has no session. */
export const fetchCloudProviders = () =>
	cached('ow:providers:cloud', () =>
		apiGet<Provider[]>('/api/v1/oauth/providers?enabled_only=true&cloud_only=true')
	);
