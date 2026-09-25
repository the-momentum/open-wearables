<script lang="ts">
	import Send from '@lucide/svelte/icons/send';
	import { enhance } from '$app/forms';
	import Button from '$lib/components/ui/Button.svelte';
	import { MICRO, MONO } from '$lib/components/ui/typography';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';
	import type { EventType, Subscription } from '$lib/webhooks/types';

	let {
		subscription,
		types,
		message
	}: { subscription: Subscription; types: EventType[]; message?: string } = $props();

	// What this subscription actually listens for; a test of something it filters
	// out would be delivered nowhere and look like a failure.
	const choices = $derived(
		subscription.filter_types?.length
			? types.filter((type) => subscription.filter_types!.includes(type.name))
			: types
	);

	let eventType = $state('');
	let sent = $state(false);

	$effect(() => {
		if (!eventType && choices.length > 0) eventType = choices[0].name;
	});

	const submit = createSubmitFlag(() => (sent = true));
</script>

<form
	method="POST"
	action="?/test"
	class="flex flex-wrap items-center gap-2"
	use:enhance={submit.enhance}
>
	<input type="hidden" name="id" value={subscription.id} />

	<label class="sr-only" for="test-{subscription.id}">Event to send</label>
	<select
		id="test-{subscription.id}"
		name="event_type"
		bind:value={eventType}
		class="h-8 w-full min-w-0 rounded-md border border-border bg-surface px-2 sm:w-auto
			sm:max-w-xs {MONO}"
	>
		{#each choices as choice (choice.name)}
			<option value={choice.name}>{choice.name}</option>
		{/each}
	</select>

	<Button type="submit" variant="outline" size="sm" disabled={submit.submitting}>
		<Send size={13} aria-hidden="true" />
		{submit.submitting ? 'Sending…' : 'Send test'}
	</Button>

	{#if message}
		<span class="{MICRO} text-danger">{message}</span>
	{:else if sent}
		<!-- Svix queues it, so it turns up in the list below on the next load
		     rather than immediately. -->
		<span class={MICRO}>Sent — it will appear below once delivered.</span>
	{/if}
</form>
