/**
 * Mirrors backend `EndpointResponse`. A subscription, not "a webhook": the row
 * is a standing request, and the deliveries under it are the webhooks.
 */
export type Subscription = {
	id: string;
	url: string;
	description: string | null;
	/** Empty or null means every event type. */
	filter_types: string[] | null;
	/** Set to follow one user only. */
	user_id: string | null;
};

/** Mirrors `EventTypeResponse`. */
export type EventType = {
	name: string;
	description: string;
	/** The granular `series.*` events a group stands for. */
	child_events: string[] | null;
};

/** Mirrors `WebhookMessageResponse` — the event, as sent. */
export type WebhookMessage = {
	id: string;
	eventType: string;
	eventId: string | null;
	timestamp: string;
	payload: Record<string, unknown> | null;
};

/** Mirrors `WebhookMessageAttemptResponse` — one delivery of one message. */
export type Delivery = {
	id: string;
	msgId: string;
	url: string;
	response: string;
	responseStatusCode: number;
	responseDurationMs: number;
	status: number;
	statusText: string | null;
	triggerType: number;
	timestamp: string;
	msg: WebhookMessage | null;
};

/** Svix pages by an opaque iterator rather than by offset. */
export type WebhookPage<T> = {
	data: T[];
	done: boolean;
	iterator: string | null;
	prevIterator: string | null;
};
