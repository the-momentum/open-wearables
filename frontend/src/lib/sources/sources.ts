import type { DeviceTypePriority, ProviderPriority } from '$lib/settings/types';
import type { DataSource, SourceGroup } from './types';

/** Where the backend ranks a provider or device type missing from the priority lists. */
const UNRANKED = 99;

/**
 * Best first, the order the backend uses when two sources cover the same day:
 * provider priority, then device type priority, then device model.
 */
export function rankSources(
	sources: DataSource[],
	providers: ProviderPriority[],
	deviceTypes: DeviceTypePriority[]
): DataSource[] {
	const providerRank = new Map(providers.map((entry) => [entry.provider, entry.priority]));
	const typeRank = new Map(deviceTypes.map((entry) => [entry.device_type, entry.priority]));
	const rank = (source: DataSource) => [
		providerRank.get(source.provider) ?? UNRANKED,
		(source.device_type ? typeRank.get(source.device_type) : undefined) ?? UNRANKED
	];
	return [...sources].sort((a, b) => {
		const [providerA, typeA] = rank(a);
		const [providerB, typeB] = rank(b);
		return (
			providerA - providerB ||
			typeA - typeB ||
			(a.device_model ?? '').localeCompare(b.device_model ?? '')
		);
	});
}

/** One group per provider, in the order of its best source. */
export function groupByProvider(ranked: DataSource[]): SourceGroup[] {
	const groups = new Map<string, DataSource[]>();
	for (const source of ranked) {
		groups.set(source.provider, [...(groups.get(source.provider) ?? []), source]);
	}
	return [...groups].map(([provider, sources]) => ({ provider, sources }));
}

/** The device's model, by its marketing name when the API resolves one. */
export const deviceOf = (source: DataSource) => source.device_name ?? source.device_model;

/** No model means data the provider keeps per account rather than per device: dailies, sleep. */
export const sourceTitle = (source: DataSource) => deviceOf(source) ?? 'No device reported';

/** The provider naming itself: its slug, or one built on it (`google_health_api`, `apple_health_sdk`). */
const namesProvider = (name: string, provider: string) =>
	name === provider || name.startsWith(`${provider}_`);

/**
 * The provider's own name for the source, when it adds something: a device's
 * given name ("Kuba's Apple Watch") or the app that wrote the data. The
 * provider's own identifier says nothing the logo does not.
 */
export function sourceDetail(source: DataSource): string | null {
	const name = source.source?.trim();
	if (!name || namesProvider(name.toLowerCase(), source.provider) || name === deviceOf(source)) {
		return null;
	}
	return name;
}
