<script lang="ts">
	import type { Component, Snippet } from 'svelte';
	import { MICRO } from '$lib/components/ui/typography';

	let {
		icon: Icon,
		label,
		value,
		children
	}: {
		icon: Component;
		label: string;
		/** A number, or a snippet where a number will not do. */
		value?: string;
		children?: Snippet;
	} = $props();
</script>

<div class="flex items-center gap-2">
	<Icon size={15} aria-hidden="true" class="shrink-0 text-muted-foreground/60" />
	<div class="min-w-0 flex-1">
		<dd class="flex h-5 items-center">
			{#if children}
				{@render children()}
			{:else}
				<span class="truncate text-sm font-medium text-foreground tabular-nums">{value}</span>
			{/if}
		</dd>
		<dt class="truncate {MICRO}">{label}</dt>
	</div>
</div>
