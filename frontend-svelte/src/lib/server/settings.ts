import { apiDelete, apiGet, apiPatch, apiPost, apiPublicPost, apiPut } from './api';
import { byName } from '$lib/providers/labels';
import type {
	ApiKey,
	ApiKeySecret,
	Application,
	ApplicationSecret,
	Developer,
	DeviceTypePriority,
	Invitation,
	ProviderPriority,
	ProviderSetting
} from '$lib/settings/types';

const KEYS = '/api/v1/developer/api-keys';
const APPS = '/api/v1/applications';
const PROVIDERS = '/api/v1/oauth/providers';
const INVITATIONS = '/api/v1/invitations';

export const listApiKeys = (accessToken: string) => apiGet<ApiKey[]>(KEYS, accessToken);

export const createApiKey = (name: string, accessToken: string) =>
	apiPost<ApiKeySecret>(KEYS, accessToken, { name });

export const renameApiKey = (id: string, name: string, accessToken: string) =>
	apiPatch<ApiKey>(`${KEYS}/${id}`, accessToken, { name });

export const rotateApiKey = (id: string, accessToken: string) =>
	apiPost<ApiKeySecret>(`${KEYS}/${id}/rotate`, accessToken);

export const deleteApiKey = (id: string, accessToken: string) =>
	apiDelete(`${KEYS}/${id}`, accessToken);

export const listApplications = (accessToken: string) => apiGet<Application[]>(APPS, accessToken);

export const createApplication = (name: string, accessToken: string) =>
	apiPost<ApplicationSecret>(APPS, accessToken, { name });

export const rotateApplicationSecret = (appId: string, accessToken: string) =>
	apiPost<ApplicationSecret>(`${APPS}/${appId}/rotate-secret`, accessToken);

export const deleteApplication = (appId: string, accessToken: string) =>
	apiDelete(`${APPS}/${appId}`, accessToken);

/** Every provider, enabled or not: this is the page that decides which. */
export const listProviderSettings = async (accessToken: string) =>
	byName(await apiGet<ProviderSetting[]>(PROVIDERS, accessToken));

export const saveProviderSettings = (providers: Record<string, boolean>, accessToken: string) =>
	apiPut<ProviderSetting[]>(PROVIDERS, accessToken, { providers });

export const setLiveSyncMode = (provider: string, mode: string, accessToken: string) =>
	apiPut<ProviderSetting>(`${PROVIDERS}/${provider}`, accessToken, { live_sync_mode: mode });

/** Both priority lists answer with `{ items }`, which the pages do not need. */
export const listProviderPriorities = async (accessToken: string) =>
	(await apiGet<{ items: ProviderPriority[] }>('/api/v1/priorities/providers', accessToken)).items;

export const listDeviceTypePriorities = async (accessToken: string) =>
	(await apiGet<{ items: DeviceTypePriority[] }>('/api/v1/priorities/device-types', accessToken))
		.items;

export const saveProviderPriorities = (priorities: unknown[], accessToken: string) =>
	apiPut('/api/v1/priorities/providers', accessToken, { priorities });

export const saveDeviceTypePriorities = (priorities: unknown[], accessToken: string) =>
	apiPut('/api/v1/priorities/device-types', accessToken, { priorities });

export const listDevelopers = (accessToken: string) =>
	apiGet<Developer[]>('/api/v1/developers', accessToken);

export const removeDeveloper = (id: string, accessToken: string) =>
	apiDelete(`/api/v1/developers/${id}`, accessToken);

export const listInvitations = (accessToken: string) =>
	apiGet<Invitation[]>(INVITATIONS, accessToken);

export const createInvitation = (email: string, accessToken: string) =>
	apiPost<Invitation>(INVITATIONS, accessToken, { email });

export const resendInvitation = (id: string, accessToken: string) =>
	apiPost(`${INVITATIONS}/${id}/resend`, accessToken);

export const revokeInvitation = (id: string, accessToken: string) =>
	apiDelete(`${INVITATIONS}/${id}`, accessToken);

/** Public: the person accepting has no account until this returns one. */
export const acceptInvitation = (body: {
	token: string;
	first_name: string;
	last_name: string;
	password: string;
}) => apiPublicPost<Developer>(`${INVITATIONS}/accept`, body);

export const changePassword = (
	body: { current_password: string; new_password: string; confirm_password: string },
	accessToken: string
) => apiPost('/api/v1/auth/change-password', accessToken, body);
