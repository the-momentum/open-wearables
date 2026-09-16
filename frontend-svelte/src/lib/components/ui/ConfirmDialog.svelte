<script lang="ts">
	import type { Snippet } from 'svelte';
	import { enhance } from '$app/forms';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
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

		<div class="mt-1 flex justify-end gap-2">
			<Button variant="outline" onclick={() => (open = false)}>Cancel</Button>
			<Button
				type="submit"
				disabled={submit.submitting}
				class={destructive ? 'bg-danger text-danger-foreground hover:bg-danger/90' : undefined}
			>
				{submit.submitting ? busyLabel : confirmLabel}
			</Button>
		</div>
	</form>
</Sheet>
