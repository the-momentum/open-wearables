import type { Tone } from '$lib/components/ui/tone';
import type { Connection } from './types';

const TONE: Record<Connection['status'], Tone> = {
	active: 'success',
	expired: 'warning',
	revoked: 'danger'
};

export const connectionTone = (status: Connection['status']): Tone => TONE[status] ?? 'neutral';
