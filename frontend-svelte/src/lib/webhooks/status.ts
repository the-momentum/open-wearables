import type { Tone } from '$lib/components/ui/tone';

/** Mirrors Svix `MessageStatus`, which the API passes through as an integer. */
const STATUS: Record<number, { label: string; tone: Tone }> = {
	0: { label: 'Delivered', tone: 'success' },
	1: { label: 'Pending', tone: 'neutral' },
	2: { label: 'Failed', tone: 'danger' },
	3: { label: 'Sending', tone: 'primary' }
};

export const statusOf = (status: number) =>
	STATUS[status] ?? { label: `Status ${status}`, tone: 'neutral' as Tone };

/** The filter offers only what the endpoint accepts. */
export const STATUS_OPTIONS = Object.entries(STATUS).map(([value, { label }]) => ({
	value,
	label
}));

/** Mirrors Svix `MessageAttemptTriggerType`. */
export const triggerOf = (trigger: number) => (trigger === 1 ? 'Retry' : 'Scheduled');

/**
 * Svix keeps the response body and the event payload behind a `with_content`
 * flag that v2 of its SDK defaults to **false**, so both arrive empty until the
 * backend asks for them. An empty object is not "the provider sent nothing" —
 * it is "nobody asked", and the two must not read the same.
 */
export const hasContent = (value: unknown): boolean => {
	if (value === null || value === undefined) return false;
	if (typeof value === 'string') return value.trim().length > 0;
	return Object.keys(value as object).length > 0;
};
