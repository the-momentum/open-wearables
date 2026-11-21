<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import Send from '@lucide/svelte/icons/send';
	import { enhance } from '$app/forms';
	import Button from '$lib/components/ui/Button.svelte';
	import { SELECT } from '$lib/components/ui/field';
	import { ICON } from '$lib/components/ui/icon';
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
	class="flex min-w-0 flex-col gap-2"
	use:enhance={submit.enhance}
>
	<input type="hidden" name="id" value={subscription.id} />

	<span class={MICRO}>Send test</span>
	<label class="sr-only" for="test-{subscription.id}">Event to send</label>
	<div class="flex flex-col items-start gap-2 sm:flex-row sm:items-center">
		<!-- A select is as wide as its longest option, which would outgrow a phone. -->
		<div class="relative flex w-full min-w-0 items-center sm:flex-1">
			<select
				id="test-{subscription.id}"
				name="event_type"
				bind:value={eventType}
				class="w-full min-w-0 {SELECT.md} {MONO}"
			>
				{#each choices as choice (choice.name)}
					<option value={choice.name}>{choice.name}</option>
				{/each}
			</select>
			<ChevronDown
				size={ICON.xs}
				aria-hidden="true"
				class="pointer-events-none absolute right-2 text-muted-foreground"
			/>
		</div>

		<Button type="submit" variant="outline" size="sm" disabled={submit.submitting}>
			<Send size={ICON.xs} aria-hidden="true" />
			{submit.submitting ? 'Sending…' : 'Send test'}
		</Button>
	</div>

	{#if message}
		<span class="{MICRO} text-danger">{message}</span>
	{:else if sent}
		<!-- Svix queues it, so it turns up in the list below on the next load
		     rather than immediately. -->
		<span class={MICRO}>Sent - it will appear below once delivered.</span>
	{/if}
</form>
