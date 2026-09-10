<script lang="ts">
	import Check from '@lucide/svelte/icons/check';
	import Link2 from '@lucide/svelte/icons/link-2';
	import Smartphone from '@lucide/svelte/icons/smartphone';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Upload from '@lucide/svelte/icons/upload';
	import { enhance } from '$app/forms';
	import { page } from '$app/state';
	import ActionMenu from '$lib/components/ui/ActionMenu.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import { menuItemClass } from '$lib/components/ui/menu';
	import { pairingLink } from '$lib/pairing/links';
	import type { UserDetail } from '$lib/users/types';
	import { createCopier } from '$lib/utils/clipboard.svelte';

	let { user, ondelete }: { user: UserDetail; ondelete: () => void } = $props();

	let menuOpen = $state(false);
	const copier = createCopier();

	function copyPairingLink() {
		menuOpen = false;
		copier.copy(pairingLink(page.url.origin, user.id));
	}
</script>

<div class="flex shrink-0 items-center gap-2">
	<!-- Short labels so the row sits beside the identity instead of wrapping
	     under it; the full wording is in the title. -->
	<Button
		variant="outline"
		onclick={copyPairingLink}
		title="Copy the pairing link for this user"
		class="hidden px-3 sm:inline-flex"
	>
		{#if copier.copied}
			<Check size={15} aria-hidden="true" class="text-success" />
			Copied
		{:else}
			<Link2 size={15} aria-hidden="true" />
			Pairing link
		{/if}
	</Button>

	<form method="POST" action="?/invite" use:enhance class="hidden sm:block">
		<Button
			type="submit"
			variant="outline"
			title="Generate a code to connect the Open Wearables app"
			class="px-3"
		>
			<Smartphone size={15} aria-hidden="true" />
			Mobile app
		</Button>
	</form>

	<ActionMenu bind:open={menuOpen} label="More user actions" title="User actions">
		<button type="button" onclick={copyPairingLink} class="{menuItemClass()} sm:hidden">
			<Link2 size={16} aria-hidden="true" />
			Copy pairing link
		</button>

		<form method="POST" action="?/invite" use:enhance class="sm:hidden">
			<button type="submit" class={menuItemClass()}>
				<Smartphone size={16} aria-hidden="true" />
				Connect mobile app
			</button>
		</form>

		<button
			type="button"
			disabled
			title="The Apple Health import is a multipart upload and is not built here yet"
			class={menuItemClass()}
		>
			<Upload size={16} aria-hidden="true" />
			Upload Apple Health XML
		</button>

		<button
			type="button"
			onclick={() => {
				menuOpen = false;
				ondelete();
			}}
			class={menuItemClass(true)}
		>
			<Trash2 size={16} aria-hidden="true" />
			Delete user
		</button>
	</ActionMenu>
</div>
