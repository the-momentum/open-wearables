<script lang="ts">
	import Plus from '@lucide/svelte/icons/plus';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';

	let { inserted, updated }: { inserted: number; updated: number } = $props();
</script>

{#if inserted === 0 && updated === 0}
	<span>Nothing saved</span>
{:else}
	{#if inserted > 0}
		<span class="flex items-center gap-1" title="Records created">
			<Plus size={12} aria-hidden="true" class="text-muted-foreground/60" />
			<span class="text-foreground/80 tabular-nums">{inserted}</span>
			new
		</span>
	{/if}
	{#if updated > 0}
		<span class="flex items-center gap-1" title="Records already held, refreshed">
			<RefreshCw size={11} aria-hidden="true" class="text-muted-foreground/60" />
			<span class="text-foreground/80 tabular-nums">{updated}</span>
			updated
		</span>
	{/if}
{/if}
