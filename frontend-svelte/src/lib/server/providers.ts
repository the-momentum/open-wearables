import { apiGet } from './api';
import { cached } from './cache';

export type Provider = {
	provider: string;
	name: string;
	has_cloud_api: boolean;
	is_enabled: boolean;
	/** Relative to the API base; a static file, so the browser fetches it directly. */
	icon_url: string;
};

const TTL_SECONDS = 60;

/** The API orders them by when they were added to its enum, which says nothing. */
const byName = (providers: Provider[]) =>
	[...providers].sort((a, b) => a.name.localeCompare(b.name));

/** Enabled only: a filter chip for a provider nobody can connect is noise. */
export const fetchProviders = async (accessToken: string) =>
	byName(
		await cached('ow:providers:enabled', TTL_SECONDS, () =>
			apiGet<Provider[]>('/api/v1/oauth/providers?enabled_only=true', accessToken)
		)
	);

/** Public: the pairing page has no session. */
export const fetchCloudProviders = async () =>
	byName(
		await cached('ow:providers:cloud', TTL_SECONDS, () =>
			apiGet<Provider[]>('/api/v1/oauth/providers?enabled_only=true&cloud_only=true')
		)
	);
