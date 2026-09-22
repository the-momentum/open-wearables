import { apiDelete, apiGet, apiPatch, apiPost } from './api';
import type { Delivery, EventType, Subscription, WebhookPage } from '$lib/webhooks/types';

const ENDPOINTS = '/api/v1/webhooks/endpoints';

export const listSubscriptions = (accessToken: string) =>
	apiGet<Subscription[]>(ENDPOINTS, accessToken);

export const listEventTypes = (accessToken: string) =>
	apiGet<EventType[]>('/api/v1/webhooks/event-types', accessToken);

export type SubscriptionInput = {
	url: string;
	description: string | null;
	filter_types: string[];
	user_id: string | null;
};

export const createSubscription = (input: SubscriptionInput, accessToken: string) =>
	apiPost<Subscription>(ENDPOINTS, accessToken, input);

export const updateSubscription = (id: string, input: SubscriptionInput, accessToken: string) =>
	apiPatch<Subscription>(`${ENDPOINTS}/${id}`, accessToken, input);

export const deleteSubscription = (id: string, accessToken: string) =>
	apiDelete(`${ENDPOINTS}/${id}`, accessToken);

export const sendTestEvent = (id: string, eventType: string, accessToken: string) =>
	apiPost<{ message: string }>(`${ENDPOINTS}/${id}/test`, accessToken, { event_type: eventType });

export type DeliveryQuery = {
	limit?: number;
	iterator?: string;
	status?: string;
	eventTypes?: string[];
};

export function listDeliveries(
	id: string,
	accessToken: string,
	{ limit = 20, iterator = '', status = '', eventTypes = [] }: DeliveryQuery = {}
): Promise<WebhookPage<Delivery>> {
	const params = new URLSearchParams({ limit: String(limit) });
	if (iterator) params.set('iterator', iterator);
	if (status) params.set('status', status);
	for (const type of eventTypes) params.append('event_types', type);

	return apiGet<WebhookPage<Delivery>>(`${ENDPOINTS}/${id}/attempts?${params}`, accessToken);
}
