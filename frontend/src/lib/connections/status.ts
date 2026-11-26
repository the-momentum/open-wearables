import type { Tone } from '$lib/components/ui/tone';
import type { Connection } from './types';

const TONE: Record<Connection['status'], Tone> = {
	active: 'success',
	expired: 'warning',
	revoked: 'danger'
};

export const connectionTone = (status: Connection['status']): Tone => TONE[status] ?? 'neutral';

/** What a status means for the reader, for the tooltip on a provider pill. */
const NOTE: Record<Connection['status'], string> = {
	active: 'Connected',
	expired: 'Authorisation expired: the user must reconnect',
	revoked: 'Disconnected: access was revoked'
};

export const connectionNote = (status: Connection['status']): string => NOTE[status] ?? status;
