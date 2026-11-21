<script lang="ts">
	import Check from '@lucide/svelte/icons/check';
	import Link2 from '@lucide/svelte/icons/link-2';
	import Smartphone from '@lucide/svelte/icons/smartphone';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Upload from '@lucide/svelte/icons/upload';
	import { enhance } from '$app/forms';
	import ActionMenu from '$lib/components/ui/ActionMenu.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import { ICON } from '$lib/components/ui/icon';
	import { menuItemClass } from '$lib/components/ui/menu';
	import { fetchPairingLink } from '$lib/pairing/links';
	import type { User } from '$lib/users/types';
	import { createCopier } from '$lib/utils/clipboard.svelte';

	let { user, ondelete }: { user: User; ondelete: () => void } = $props();

	let menuOpen = $state(false);
	const copier = createCopier();

	function copyPairingLink() {
		menuOpen = false;
		copier.copyPending(fetchPairingLink(user.id));
	}
</script>

<div class="flex shrink-0 items-center gap-2">
	<!-- Short labels so the row sits beside the identity instead of wrapping
	     under it; the full wording is in the title. -->
	<Button
		variant="outline"
		onclick={copyPairingLink}
		title="Copy the pairing link for this user"
		class="hidden sm:inline-flex"
	>
		{#if copier.copied}
			<Check size={ICON.sm} aria-hidden="true" class="text-success" />
			Copied
		{:else}
			<Link2 size={ICON.sm} aria-hidden="true" />
			Pairing link
		{/if}
	</Button>

	<form method="POST" action="?/invite" use:enhance class="hidden sm:block">
		<Button
			type="submit"
			variant="outline"
			title="Generate a code to connect the Open Wearables app"
		>
			<Smartphone size={ICON.sm} aria-hidden="true" />
			Mobile app
		</Button>
	</form>

	<!-- Bordered among the buttons; alone on a phone, a bare glyph. -->
	<ActionMenu
		bind:open={menuOpen}
		label="More user actions"
		title="User actions"
		class="max-sm:size-9 max-sm:min-h-0 max-sm:border-0 max-sm:px-0 max-sm:text-muted-foreground"
	>
		<button type="button" onclick={copyPairingLink} class="{menuItemClass()} sm:hidden">
			<Link2 size={ICON.sm} aria-hidden="true" />
			Copy pairing link
		</button>

		<form method="POST" action="?/invite" use:enhance class="sm:hidden">
			<button type="submit" class={menuItemClass()}>
				<Smartphone size={ICON.sm} aria-hidden="true" />
				Connect mobile app
			</button>
		</form>

		<button
			type="button"
			disabled
			title="The Apple Health import is a multipart upload and is not built here yet"
			class={menuItemClass()}
		>
			<Upload size={ICON.sm} aria-hidden="true" />
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
			<Trash2 size={ICON.sm} aria-hidden="true" />
			Delete user
		</button>
	</ActionMenu>
</div>
