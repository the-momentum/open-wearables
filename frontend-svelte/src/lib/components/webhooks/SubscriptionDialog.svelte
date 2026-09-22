<script lang="ts">
	import { enhance } from '$app/forms';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { createDialogSubmit } from '$lib/utils/forms.svelte';
	import EventPicker from './EventPicker.svelte';
	import type { EventType, Subscription } from '$lib/webhooks/types';

	let {
		open = $bindable(false),
		subscription = null,
		types,
		message
	}: {
		open?: boolean;
		subscription?: Subscription | null;
		types: EventType[];
		message?: string;
	} = $props();

	const editing = $derived(subscription !== null);
	const submit = createDialogSubmit(() => (open = false));

	// The dialog stays mounted between openings and `enhance` resets the form on
	// success, so the fields are local state re-seeded each time it opens.
	let url = $state('');
	let description = $state('');
	let userId = $state('');
	let chosen = $state<string[]>([]);

	$effect(() => {
		if (!open) return;
		url = subscription?.url ?? '';
		description = subscription?.description ?? '';
		userId = subscription?.user_id ?? '';
		chosen = [...(subscription?.filter_types ?? [])];
	});

	const field =
		'min-h-11 rounded-lg border border-border bg-surface px-3 text-sm placeholder:text-muted-foreground/60';
</script>

<Sheet bind:open title={editing ? 'Edit subscription' : 'New subscription'}>
	<form
		method="POST"
		action={editing ? '?/update' : '?/create'}
		class="flex flex-col gap-4 px-4 pb-2"
		use:enhance={submit.enhance}
	>
		{#if subscription}
			<input type="hidden" name="id" value={subscription.id} />
		{/if}
		{#each chosen as name (name)}
			<input type="hidden" name="filter_types" value={name} />
		{/each}

		{#if message}
			<Alert>{message}</Alert>
		{/if}

		<label class="flex flex-col gap-1.5">
			<span class={MICRO}>Endpoint URL</span>
			<input
				name="url"
				type="url"
				required
				bind:value={url}
				placeholder="https://api.example.com/webhooks"
				class={field}
			/>
		</label>

		<label class="flex flex-col gap-1.5">
			<span class={MICRO}>Description</span>
			<input
				name="description"
				bind:value={description}
				placeholder="What this subscription is for"
				class={field}
			/>
		</label>

		<label class="flex flex-col gap-1.5">
			<span class={MICRO}>One user only</span>
			<input
				name="user_id"
				bind:value={userId}
				placeholder="User ID — leave empty for every user"
				class={field}
			/>
		</label>

		<fieldset class="flex flex-col gap-2">
			<legend class={MICRO}>Events — none chosen means every event</legend>
			<EventPicker {types} bind:chosen />
		</fieldset>

		<div class="flex justify-end gap-2 pt-1">
			<Button type="button" variant="outline" onclick={() => (open = false)}>Cancel</Button>
			<Button type="submit" disabled={submit.submitting}>
				{submit.submitting ? 'Saving…' : editing ? 'Save changes' : 'Create subscription'}
			</Button>
		</div>
	</form>
</Sheet>
