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

/** No model means data the provider keeps per account rather than per device: dailies, sleep. */
export const sourceTitle = (source: DataSource) => source.device_name ?? 'No device reported';

const SLUG = /^[a-z0-9_]+$/;

/**
 * The provider's own name for the source, when it adds something: a device's
 * given name ("Kuba's Apple Watch") or the app that wrote the data. A provider
 * slug like `garmin` or `google_health_api` says nothing the logo does not.
 */
export function sourceDetail(source: DataSource): string | null {
	const name = source.source?.trim();
	if (!name || SLUG.test(name) || name === source.device_name) return null;
	return name;
}
