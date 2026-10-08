import { apiGet } from './api';
import { cached, forget } from './cache';
import { byName } from '$lib/providers/labels';

export type Provider = {
	provider: string;
	name: string;
	has_cloud_api: boolean;
	is_enabled: boolean;
	/** Relative to the API base; a static file, so the browser fetches it directly. */
	icon_url: string;
};

const TTL_SECONDS = 60;
const KEY = 'ow:providers:all';

/**
 * Every provider, enabled or not, cached once; the narrower lists are cut from
 * it. A connection can outlive its provider being switched off. Public, so the
 * pairing page needs no session.
 */
export const fetchAllProviders = async (accessToken?: string) =>
	byName(
		await cached(KEY, TTL_SECONDS, () => apiGet<Provider[]>('/api/v1/oauth/providers', accessToken))
	);

/** After a save in Settings, so a provider switched off leaves every list at once. */
export const forgetProviders = () => forget(KEY);

/** Enabled only: a filter chip for a provider nobody can connect is noise. */
export const fetchProviders = async (accessToken: string) =>
	(await fetchAllProviders(accessToken)).filter((provider) => provider.is_enabled);

/** What the pairing page offers: enabled, and reached through a cloud OAuth flow. */
export const fetchCloudProviders = async () =>
	(await fetchAllProviders()).filter((provider) => provider.is_enabled && provider.has_cloud_api);
