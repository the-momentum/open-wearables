<script lang="ts">
	import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';
	import { fullName } from '$lib/users/avatar';
	import type { User } from '$lib/users/types';

	let {
		open = $bindable(false),
		user,
		message
	}: { open?: boolean; user: User | null; message?: string } = $props();

	const who = $derived(user ? fullName(user) || user.email || 'this user' : '');
</script>

{#if user}
	<ConfirmDialog
		bind:open
		title="Delete user"
		action="?/delete"
		confirmLabel="Delete user"
		busyLabel="Deleting…"
		fields={{ id: user.id }}
		{message}
		destructive
	>
		Delete <span class="font-medium">{who}</span>? Their synced data goes with them and this cannot
		be undone.
	</ConfirmDialog>
{/if}
