import { apiPost } from './api';

/** Mirrors backend `UserInvitationCodeGenerated`. */
export type InvitationCode = {
	id: string;
	code: string;
	user_id: string;
	expires_at: string;
	created_at: string;
	/** Opens the Open Wearables Connect app with this server and code. */
	invite_url: string;
	/** invite_url as a QR code, an SVG document rendered by the instance. */
	qr_svg: string;
};

export const generateInvitationCode = (userId: string, accessToken: string) =>
	apiPost<InvitationCode>(`/api/v1/users/${userId}/invitation-code`, accessToken);

/** Emails the user's current code; to their own address when `email` is empty. */
export const emailInvitationCode = (userId: string, email: string, accessToken: string) =>
	apiPost<{ sent_to: string; expires_at: string }>(
		`/api/v1/users/${userId}/invitation-code/email`,
		accessToken,
		email ? { email } : {}
	);
