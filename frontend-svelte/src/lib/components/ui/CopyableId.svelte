<script lang="ts">
	import Check from '@lucide/svelte/icons/check';
	import Copy from '@lucide/svelte/icons/copy';
	import { createCopier } from '$lib/utils/clipboard.svelte';

	let {
		value,
		label = 'ID',
		visible = 4
	}: { value: string; label?: string; visible?: number } = $props();

	const copier = createCopier();
</script>

<!-- z-10 keeps this above the row-wide overlay link, so copying does not also
     open the row. -->
<span class="relative z-10 inline-flex items-center gap-1">
	<code
		title={value}
		class="rounded bg-surface-muted px-1.5 py-0.5 font-mono text-xs text-foreground/80"
	>
		{value.slice(0, visible)}…
	</code>
	<button
		type="button"
		onclick={() => copier.copy(value)}
		aria-label={copier.copied ? `${label} copied` : `Copy ${label}`}
		class="grid size-7 place-items-center rounded text-muted-foreground transition-colors
			hover:text-foreground"
	>
		{#if copier.copied}
			<Check size={13} aria-hidden="true" class="text-success" />
		{:else}
			<Copy size={13} aria-hidden="true" />
		{/if}
	</button>
</span>
