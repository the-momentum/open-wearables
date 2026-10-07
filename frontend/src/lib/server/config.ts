import { apiGet } from './api';
import { optional } from './optional';
import type { Features } from '$lib/config/features';

/** Mirrors `ConfigResponse`. A backend older than a flag leaves it out. */
export type AppConfig = {
	outgoing_webhooks_enabled: boolean;
	data_lifecycle_enabled?: boolean;
	email_enabled?: boolean;
};

export const fetchFeatures = async (accessToken: string): Promise<Features> => {
	const config = await apiGet<AppConfig>('/api/v1/config', accessToken);
	return {
		lifecycle: config.data_lifecycle_enabled !== false,
		email: config.email_enabled !== false,
		// Off by default: without it the webhook endpoints answer 503.
		webhooks: config.outgoing_webhooks_enabled === true
	};
};

/** Unreadable config switches nothing off: each page then reports what is wrong itself. */
export const readFeatures = (accessToken: string) =>
	optional(fetchFeatures(accessToken), { lifecycle: true, email: true, webhooks: true });
