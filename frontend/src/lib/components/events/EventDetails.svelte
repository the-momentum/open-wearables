<script lang="ts">
	import type { Snippet } from 'svelte';
	import DeleteAction from './DeleteAction.svelte';

	let {
		children,
		deleteLabel,
		ondelete,
		note = ''
	}: {
		children: Snippet;
		deleteLabel: string;
		ondelete: () => void;
		/** Small print opposite the delete action - what is stored but not shown. */
		note?: string;
	} = $props();
</script>

<div class="flex flex-col gap-5">
	{@render children()}

	<div class="flex items-center justify-between gap-3 border-t border-border pt-3">
		<span class="text-xs text-muted-foreground">{note}</span>
		<DeleteAction label={deleteLabel} onclick={ondelete} />
	</div>
</div>
