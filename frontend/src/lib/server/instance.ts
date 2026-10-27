import { apiGet, apiPatch } from './api';

/** Mirrors backend `InstanceSettingsRead`. */
export type InstanceSettings = {
	organization_name: string | null;
	logo_url: string | null;
	support_email: string | null;
	privacy_policy_url: string | null;
	terms_url: string | null;
	require_acceptance: boolean;
	legal_documents_version: number;
	updated_at: string | null;
};

export type InstanceSettingsUpdate = Partial<
	Pick<
		InstanceSettings,
		| 'organization_name'
		| 'logo_url'
		| 'support_email'
		| 'privacy_policy_url'
		| 'terms_url'
		| 'require_acceptance'
	> & {
		/** Publishes a new version of documents whose URLs stay the same. */
		bump_legal_documents_version: boolean;
	}
>;

const SETTINGS = '/api/v1/instance/settings';

export const fetchInstanceSettings = (accessToken: string) =>
	apiGet<InstanceSettings>(SETTINGS, accessToken);

/** An empty field is sent as null, which clears it on the backend. */
export const saveInstanceSettings = (update: InstanceSettingsUpdate, accessToken: string) =>
	apiPatch<InstanceSettings>(SETTINGS, accessToken, update);
