<script lang="ts">
	import Check from '@lucide/svelte/icons/check';
	import Link2 from '@lucide/svelte/icons/link-2';
	import Pencil from '@lucide/svelte/icons/pencil';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import ActionMenu from '$lib/components/ui/ActionMenu.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import { ICON } from '$lib/components/ui/icon';
	import { menuItemClass } from '$lib/components/ui/menu';
	import { fullName } from '$lib/users/avatar';
	import { fetchPairingLink } from '$lib/pairing/links';
	import { getRowActions } from '$lib/users/row-actions';
	import type { User } from '$lib/users/types';
	import { createCopier } from '$lib/utils/clipboard.svelte';

	let {
		user,
		menu = false
	}: {
		user: User;
		/** One "…" behind which the three wait: a phone's row has no room for them side by side. */
		menu?: boolean;
	} = $props();

	const actions = getRowActions();
	const copier = createCopier();
	const who = $derived(fullName(user) || user.email || 'this user');

	let open = $state(false);

	// The menu closes first, so the dialog an entry opens is not stacked on the sheet.
	function run(action: () => void) {
		open = false;
		action();
	}

	const edit = () => actions.edit(user);
	const remove = () => actions.remove(user);
	const copyLink = () => copier.copyPending(fetchPairingLink(user.id));
</script>

<!-- z-10 keeps these above the row-wide overlay link in UserIdentity, so a
     click here does not also open the user. -->
<div class="relative z-10 flex items-center justify-end gap-0.5">
	{#if menu}
		<ActionMenu bind:open quiet label="Actions for {who}" title="User actions">
			<button type="button" onclick={() => run(edit)} class={menuItemClass()}>
				<Pencil size={ICON.sm} aria-hidden="true" />
				Edit user
			</button>
			<!-- Stays open, so the sheet is where the copy is confirmed. -->
			<button type="button" onclick={copyLink} class={menuItemClass()}>
				{#if copier.copied}
					<Check size={ICON.sm} aria-hidden="true" class="text-success" />
					Pairing link copied
				{:else}
					<Link2 size={ICON.sm} aria-hidden="true" />
					Copy pairing link
				{/if}
			</button>
			<button type="button" onclick={() => run(remove)} class={menuItemClass(true)}>
				<Trash2 size={ICON.sm} aria-hidden="true" />
				Delete user
			</button>
		</ActionMenu>
	{:else}
		<IconButton icon={Pencil} label="Edit {who}" onclick={edit} />
		<IconButton
			icon={copier.copied ? Check : Link2}
			label={copier.copied ? 'Pairing link copied' : `Copy pairing link for ${who}`}
			onclick={copyLink}
			class={copier.copied ? 'text-success hover:text-success' : undefined}
		/>
		<IconButton icon={Trash2} label="Delete {who}" onclick={remove} danger />
	{/if}
</div>
