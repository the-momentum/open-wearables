import { apiPost } from './api';

/** Mirrors backend `UserInvitationCodeRead`. */
export type InvitationCode = {
	id: string;
	code: string;
	user_id: string;
	expires_at: string;
	created_at: string;
};

export const generateInvitationCode = (userId: string, accessToken: string) =>
	apiPost<InvitationCode>(`/api/v1/users/${userId}/invitation-code`, accessToken);
