<script lang="ts">
	import { enhance } from '$app/forms';
	import Alert from '$lib/components/ui/Alert.svelte';
	import DialogActions from '$lib/components/ui/DialogActions.svelte';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import TextField from '$lib/components/ui/TextField.svelte';
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

		<TextField
			name="url"
			type="url"
			label="Endpoint URL"
			placeholder="https://api.example.com/webhooks"
			required
			bind:value={url}
		/>

		<TextField
			name="description"
			label="Description"
			placeholder="What this subscription is for"
			bind:value={description}
		/>

		<TextField
			name="user_id"
			label="One user only"
			placeholder="User ID — leave empty for every user"
			bind:value={userId}
		/>

		<fieldset class="flex flex-col gap-2">
			<legend class={MICRO}>Events — none chosen means every event</legend>
			<EventPicker {types} bind:chosen />
		</fieldset>

		<DialogActions
			oncancel={() => (open = false)}
			submitting={submit.submitting}
			submitLabel={editing ? 'Save changes' : 'Create subscription'}
			busyLabel="Saving…"
		/>
	</form>
</Sheet>
