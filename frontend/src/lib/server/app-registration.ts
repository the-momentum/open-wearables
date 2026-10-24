import { apiDelete, apiGet, apiPost } from './api';

/** Mirrors backend `AppRegistrationRead`. */
export type AppRegistration = {
	registered: boolean;
	instance_id: string | null;
	status: 'pending_verification' | 'active' | 'removed' | null;
	admin_email: string | null;
	marketing_consent: boolean | null;
	terms_version: string | null;
	email_verified_at: string | null;
	registered_at: string | null;
};

/** Mirrors backend `AppEntitlement`. A null limit means no limit. */
export type AppEntitlement = {
	status: string;
	plan: string;
	seat_limit: number | null;
	seats_used: number;
	rejected_claims_7d: number;
};

export type AppRegistrationCreate = {
	admin_email: string;
	accept_terms: boolean;
	marketing_consent: boolean;
};

const REGISTRATION = '/api/v1/app-registration';

export const fetchAppRegistration = (accessToken: string) =>
	apiGet<AppRegistration>(REGISTRATION, accessToken);

export const registerApp = (input: AppRegistrationCreate, accessToken: string) =>
	apiPost<AppRegistration>(REGISTRATION, accessToken, input);

export const unregisterApp = (accessToken: string) => apiDelete(REGISTRATION, accessToken);

export const fetchAppEntitlement = (accessToken: string) =>
	apiGet<AppEntitlement>(`${REGISTRATION}/entitlement`, accessToken);

/** Seat usage when the app is enabled; null otherwise or when the license server is unreachable. */
export async function appSeats(accessToken: string): Promise<AppEntitlement | null> {
	try {
		const registration = await fetchAppRegistration(accessToken);
		if (registration.status !== 'active') return null;
		return await fetchAppEntitlement(accessToken);
	} catch {
		return null;
	}
}
