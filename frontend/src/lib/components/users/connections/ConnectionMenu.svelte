<script lang="ts">
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Unlink from '@lucide/svelte/icons/unlink';
	import ActionMenu from '$lib/components/ui/ActionMenu.svelte';
	import { menuItemClass } from '$lib/components/ui/menu';

	let { label, onrevoke, onpurge }: { label: string; onrevoke: () => void; onpurge: () => void } =
		$props();

	let open = $state(false);

	function choose(action: () => void) {
		open = false;
		action();
	}
</script>

<ActionMenu bind:open label="Actions for {label}" title="{label} connection">
	<button type="button" onclick={() => choose(onrevoke)} class={menuItemClass()}>
		<Unlink size={16} aria-hidden="true" />
		Revoke connection
	</button>

	<button type="button" onclick={() => choose(onpurge)} class={menuItemClass(true)}>
		<Trash2 size={16} aria-hidden="true" />
		Delete all data
	</button>
</ActionMenu>
