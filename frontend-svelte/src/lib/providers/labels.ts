import { humanise } from '$lib/utils/text';
import type { Provider } from '$lib/server/providers';

/**
 * By the name people read, not the slug: the API orders providers by when they
 * joined its enum, which says nothing to anyone scanning a list.
 */
export const byName = <T extends { name: string }>(providers: T[]) =>
	[...providers].sort((a, b) => a.name.localeCompare(b.name));

/** What a provider needs to be shown: its slug, its name and where its logo is. */
export type ProviderBrand = Pick<Provider, 'provider' | 'name' | 'icon_url'>;

/**
 * Backend `ProviderName` values that are not OAuth connections, so `/oauth/providers`
 * never names them. `internal` is Open Wearables' own work — its sleep and
 * resilience scores — and left to `humanise()` it read as "Internal".
 */
const UNLISTED: Record<string, string> = { internal: 'OW' };

/** The backend owns provider names; an unknown slug still has to render. */
export function providerLabel(providers: Provider[], slug: string): string {
	return (
		providers.find((provider) => provider.provider === slug)?.name ??
		UNLISTED[slug] ??
		humanise(slug)
	);
}
