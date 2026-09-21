import { humanise } from '$lib/utils/text';
import type { Provider } from '$lib/server/providers';

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
