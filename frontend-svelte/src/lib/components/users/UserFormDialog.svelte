<script lang="ts">
	import { enhance } from '$app/forms';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Sheet from '$lib/components/ui/Sheet.svelte';
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

	const field =
		'min-h-11 rounded-lg border border-border bg-surface px-3 text-sm placeholder:text-muted-foreground/60';
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
			<label class="flex min-w-0 flex-1 flex-col gap-1.5">
				<span class="text-sm font-medium">First name</span>
				<input name="first_name" maxlength="100" bind:value={firstName} class={field} />
			</label>
			<label class="flex min-w-0 flex-1 flex-col gap-1.5">
				<span class="text-sm font-medium">Last name</span>
				<input name="last_name" maxlength="100" bind:value={lastName} class={field} />
			</label>
		</div>

		<label class="flex flex-col gap-1.5">
			<span class="text-sm font-medium">Email</span>
			<input name="email" type="email" bind:value={email} class={field} />
		</label>

		<label class="flex flex-col gap-1.5">
			<span class="text-sm font-medium">External user ID</span>
			<input name="external_user_id" maxlength="255" bind:value={externalId} class={field} />
			<span class="text-xs text-muted-foreground">Your own identifier for this person.</span>
		</label>

		<div class="mt-1 flex justify-end gap-2">
			<Button variant="outline" onclick={() => (open = false)}>Cancel</Button>
			<Button type="submit" disabled={submit.submitting}>
				{submit.submitting ? 'Saving…' : editing ? 'Save changes' : 'Create user'}
			</Button>
		</div>
	</form>
</Sheet>
