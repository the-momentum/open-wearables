import { apiGet, apiPatch } from './api';

/** Mirrors backend `InstanceSettingsRead`. */
export type InstanceSettings = {
	organization_name: string | null;
	logo_url: string | null;
	support_email: string | null;
	updated_at: string | null;
};

export type InstanceSettingsUpdate = Pick<
	InstanceSettings,
	'organization_name' | 'logo_url' | 'support_email'
>;

const SETTINGS = '/api/v1/instance/settings';

export const fetchInstanceSettings = (accessToken: string) =>
	apiGet<InstanceSettings>(SETTINGS, accessToken);

/** An empty field is sent as null, which clears it on the backend. */
export const saveInstanceSettings = (update: InstanceSettingsUpdate, accessToken: string) =>
	apiPatch<InstanceSettings>(SETTINGS, accessToken, update);
