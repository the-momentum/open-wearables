import type { ProviderSetting } from './types';

/** What the toggles say right now, keyed the way the bulk endpoint wants it. */
export const enabledMap = (settings: ProviderSetting[]): Record<string, boolean> =>
	Object.fromEntries(settings.map((setting) => [setting.provider, setting.is_enabled]));

/**
 * Only what the reader actually flipped. Sending the whole map would work, but
 * the count is what the save bar says, and "3 providers changed" has to be true.
 */
export const flipped = (
	settings: ProviderSetting[],
	draft: Record<string, boolean>
): ProviderSetting[] =>
	settings.filter(
		(setting) => (draft[setting.provider] ?? setting.is_enabled) !== setting.is_enabled
	);

/** How a provider is told about new data, for the ones that cannot be asked. */
export const liveSyncLabel = (mode: ProviderSetting['live_sync_mode']) =>
	mode === 'webhook' ? 'Webhook' : 'Periodic pull';
