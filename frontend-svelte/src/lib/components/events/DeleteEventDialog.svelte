<script lang="ts">
	import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';

	let {
		open = $bindable(false),
		noun,
		action,
		field,
		id
	}: {
		open?: boolean;
		/** What is being deleted, in the words the page uses for it. */
		noun: string;
		/** The form action on the page showing, e.g. `?/deleteWorkout`. */
		action: string;
		/** The form field that action reads the id from. */
		field: string;
		id: string;
	} = $props();
</script>

<ConfirmDialog
	bind:open
	title="Delete {noun}?"
	{action}
	confirmLabel="Delete"
	busyLabel="Deleting…"
	destructive
	fields={{ [field]: id }}
>
	This removes the {noun} and everything stored with it. It cannot be undone — though a later sync will
	bring it back if the provider still has it.
</ConfirmDialog>
