<script lang="ts">
	import type { Snippet } from 'svelte';
	import { enhance } from '$app/forms';
	import Alert from '$lib/components/ui/Alert.svelte';
	import DialogActions from '$lib/components/ui/DialogActions.svelte';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import { createDialogSubmit } from '$lib/utils/forms.svelte';

	let {
		open = $bindable(false),
		title,
		action,
		confirmLabel,
		busyLabel,
		fields = {},
		message,
		destructive = false,
		children
	}: {
		open?: boolean;
		title: string;
		/** Form action, e.g. `?/revokeConnection`. */
		action: string;
		confirmLabel: string;
		busyLabel: string;
		/** Hidden inputs the action needs to identify its subject. */
		fields?: Record<string, string>;
		message?: string;
		destructive?: boolean;
		children: Snippet;
	} = $props();

	const submit = createDialogSubmit(() => (open = false));
</script>

<Sheet bind:open {title}>
	<form method="POST" {action} class="flex flex-col gap-4 px-4 pb-2" use:enhance={submit.enhance}>
		{#each Object.entries(fields) as [name, value] (name)}
			<input type="hidden" {name} {value} />
		{/each}

		{#if message}
			<Alert>{message}</Alert>
		{/if}

		<div class="text-sm">{@render children()}</div>

		<DialogActions
			oncancel={() => (open = false)}
			submitting={submit.submitting}
			submitLabel={confirmLabel}
			{busyLabel}
			{destructive}
		/>
	</form>
</Sheet>
