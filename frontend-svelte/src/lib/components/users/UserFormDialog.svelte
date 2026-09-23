<script lang="ts">
	import { enhance } from '$app/forms';
	import Alert from '$lib/components/ui/Alert.svelte';
	import DialogActions from '$lib/components/ui/DialogActions.svelte';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import TextField from '$lib/components/ui/TextField.svelte';
	import type { User } from '$lib/users/types';
	import { createDialogSubmit } from '$lib/utils/forms.svelte';

	let {
		open = $bindable(false),
		user = null,
		message
	}: { open?: boolean; user?: User | null; message?: string } = $props();

	const editing = $derived(user !== null);
	const submit = createDialogSubmit(() => (open = false));

	// The dialog stays mounted between openings, and enhance resets the form on
	// success — which clears the DOM but leaves the props unchanged, so Svelte
	// has nothing to re-apply. Local state re-seeded on open avoids both.
	let firstName = $state('');
	let lastName = $state('');
	let email = $state('');
	let externalId = $state('');

	$effect(() => {
		if (!open) return;
		firstName = user?.first_name ?? '';
		lastName = user?.last_name ?? '';
		email = user?.email ?? '';
		externalId = user?.external_user_id ?? '';
	});
</script>

<Sheet bind:open title={editing ? 'Edit user' : 'Add user'}>
	<form
		method="POST"
		action={editing ? '?/update' : '?/create'}
		class="flex flex-col gap-4 px-4 pb-2"
		use:enhance={submit.enhance}
	>
		{#if user}
			<input type="hidden" name="id" value={user.id} />
		{/if}

		{#if message}
			<Alert>{message}</Alert>
		{/if}

		<!-- min-w-0: an input carries a default content width, so a flex item
		     holding one will not shrink below it and overflows instead. -->
		<div class="flex flex-col gap-3 sm:flex-row">
			<div class="min-w-0 flex-1">
				<TextField name="first_name" label="First name" maxlength={100} bind:value={firstName} />
			</div>
			<div class="min-w-0 flex-1">
				<TextField name="last_name" label="Last name" maxlength={100} bind:value={lastName} />
			</div>
		</div>

		<TextField name="email" type="email" label="Email" bind:value={email} />

		<TextField
			name="external_user_id"
			label="External user ID"
			maxlength={255}
			hint="Your own identifier for this person."
			bind:value={externalId}
		/>

		<DialogActions
			oncancel={() => (open = false)}
			submitting={submit.submitting}
			submitLabel={editing ? 'Save changes' : 'Create user'}
			busyLabel="Saving…"
		/>
	</form>
</Sheet>
