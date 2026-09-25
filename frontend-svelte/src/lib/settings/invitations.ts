import type { Tone } from '$lib/components/ui/tone';
import type { Invitation } from './types';

const TONE: Record<string, Tone> = {
	sent: 'success',
	pending: 'success',
	failed: 'danger',
	accepted: 'primary'
};

export const invitationTone = (status: string): Tone => TONE[status] ?? 'warning';

export const expired = (invitation: Invitation, now = Date.now()): boolean =>
	new Date(invitation.expires_at).getTime() < now;

/**
 * What is still worth acting on. An accepted invitation is a team member and
 * shows up in that list instead; a lapsed one is noise. A failed send stays,
 * because that one needs a human — the link can still be copied out by hand.
 */
export const outstanding = (invitations: Invitation[], now = Date.now()): Invitation[] =>
	invitations.filter((invitation) => {
		if (invitation.status === 'failed') return true;
		if (invitation.status !== 'pending' && invitation.status !== 'sent') return false;
		return !expired(invitation, now);
	});

/** The page that accepts it lives on this frontend, not on the API. */
export const inviteLink = (origin: string, token: string) =>
	`${origin}/accept-invite?token=${encodeURIComponent(token)}`;
