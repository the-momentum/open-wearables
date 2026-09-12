import type { BadgeTone } from '$lib/components/ui/Badge.svelte';
import type { Connection } from './types';

const TONE: Record<Connection['status'], BadgeTone> = {
	active: 'success',
	expired: 'warning',
	revoked: 'danger'
};

export const connectionTone = (status: Connection['status']): BadgeTone =>
	TONE[status] ?? 'neutral';
