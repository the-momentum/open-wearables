<script lang="ts">
	import type { Snippet } from 'svelte';
	import DeleteAction from './DeleteAction.svelte';

	let {
		children,
		deleteLabel,
		ondelete
	}: { children: Snippet; deleteLabel: string; ondelete: () => void } = $props();
</script>

<div class="flex flex-col gap-5 border-t border-border pt-4">
	{@render children()}

	<div class="flex justify-end border-t border-border pt-3">
		<DeleteAction label={deleteLabel} onclick={ondelete} />
	</div>
</div>
