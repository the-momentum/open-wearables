import { humanise } from '$lib/utils/text';
import type { Provider } from '$lib/server/providers';

/** The backend owns provider names; an unknown slug still has to render. */
export function providerLabel(providers: Provider[], slug: string): string {
	return providers.find((provider) => provider.provider === slug)?.name ?? humanise(slug);
}
