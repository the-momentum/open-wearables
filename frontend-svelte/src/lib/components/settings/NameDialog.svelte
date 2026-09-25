<script lang="ts">
	import { enhance } from '$app/forms';
	import Alert from '$lib/components/ui/Alert.svelte';
	import DialogActions from '$lib/components/ui/DialogActions.svelte';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import TextField from '$lib/components/ui/TextField.svelte';
	import { createDialogSubmit } from '$lib/utils/forms.svelte';

	let {
		open = $bindable(false),
		title,
		action,
		label = 'Name',
		hint,
		placeholder,
		submitLabel,
		busyLabel,
		value = '',
		fields = {},
		message
	}: {
		open?: boolean;
		/** Form action, e.g. `?/createKey`. */
		action: string;
		title: string;
		label?: string;
		hint?: string;
		placeholder?: string;
		submitLabel: string;
		busyLabel: string;
		/** Seeded each time it opens — renaming starts from the current name. */
		value?: string;
		fields?: Record<string, string>;
		message?: string;
	} = $props();

	const submit = createDialogSubmit(() => (open = false));
	let name = $state('');

	$effect(() => {
		if (open) name = value;
	});
</script>

<Sheet bind:open {title}>
	<form method="POST" {action} class="flex flex-col gap-4 px-4 pb-2" use:enhance={submit.enhance}>
		{#each Object.entries(fields) as [key, hidden] (key)}
			<input type="hidden" name={key} value={hidden} />
		{/each}

		{#if message}
			<Alert>{message}</Alert>
		{/if}

		<TextField name="name" {label} {hint} {placeholder} required bind:value={name} />

		<DialogActions
			oncancel={() => (open = false)}
			submitting={submit.submitting}
			{submitLabel}
			{busyLabel}
		/>
	</form>
</Sheet>
