<script lang="ts">
	import { enhance } from '$app/forms';
	import Alert from '$lib/components/ui/Alert.svelte';
	import DialogActions from '$lib/components/ui/DialogActions.svelte';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import TextField from '$lib/components/ui/TextField.svelte';
	import { createDialogSubmit } from '$lib/utils/forms.svelte';

	let { open = $bindable(false), message }: { open?: boolean; message?: string } = $props();

	const submit = createDialogSubmit(() => (open = false));
	let email = $state('');

	$effect(() => {
		if (open) email = '';
	});
</script>

<Sheet bind:open title="Invite a developer">
	<form
		method="POST"
		action="?/invite"
		class="flex flex-col gap-4 px-4 pb-2"
		use:enhance={submit.enhance}
	>
		{#if message}
			<Alert>{message}</Alert>
		{/if}

		<TextField
			name="email"
			type="email"
			label="Email address"
			placeholder="colleague@example.com"
			hint="They get a link by email. If it does not arrive, the link can be copied from the list."
			required
			bind:value={email}
		/>

		<DialogActions
			oncancel={() => (open = false)}
			submitting={submit.submitting}
			submitLabel="Send invitation"
			busyLabel="Sending…"
		/>
	</form>
</Sheet>
