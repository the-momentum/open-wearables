<script lang="ts">
	import Check from '@lucide/svelte/icons/check';
	import Link2 from '@lucide/svelte/icons/link-2';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import { page } from '$app/state';
	import { fullName } from '$lib/users/avatar';
	import { pairingLink } from '$lib/pairing/links';
	import { getRowActions } from '$lib/users/row-actions';
	import type { User } from '$lib/users/types';
	import { createCopier } from '$lib/utils/clipboard.svelte';

	let { user }: { user: User } = $props();

	const actions = getRowActions();
	const copier = createCopier();
	const who = $derived(fullName(user) || user.email || 'this user');

	const base =
		'grid size-8 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground';
</script>

<!-- z-10 keeps these above the row-wide overlay link in UserIdentity, so a
     click here does not also open the user. -->
<div class="relative z-10 flex items-center justify-end gap-0.5">
	<button type="button" onclick={() => actions.edit(user)} aria-label="Edit {who}" class={base}>
		<Pencil size={15} aria-hidden="true" />
	</button>
	<button
		type="button"
		onclick={() => copier.copy(pairingLink(page.url.origin, user.id))}
		aria-label={copier.copied ? 'Pairing link copied' : `Copy pairing link for ${who}`}
		class={base}
	>
		{#if copier.copied}
			<Check size={15} aria-hidden="true" class="text-success" />
		{:else}
			<Link2 size={15} aria-hidden="true" />
		{/if}
	</button>
	<button
		type="button"
		onclick={() => actions.remove(user)}
		aria-label="Delete {who}"
		class="{base} hover:bg-danger/10 hover:text-danger"
	>
		<Trash2 size={15} aria-hidden="true" />
	</button>
</div>
