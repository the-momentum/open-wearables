<script lang="ts">
	import type { Component, Snippet } from 'svelte';
	import { ICON } from '$lib/components/ui/icon';
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

<!-- The term comes first, as a description list needs; the figure is drawn first. -->
<div class="flex items-center gap-2">
	<Icon size={ICON.sm} aria-hidden="true" class="shrink-0 text-muted-foreground/60" />
	<div class="flex min-w-0 flex-1 flex-col-reverse">
		<dt class="truncate {MICRO}">{label}</dt>
		<dd class="flex min-h-5 items-center">
			{#if children}
				{@render children()}
			{:else}
				<span class="truncate text-sm font-medium text-foreground tabular-nums">{value}</span>
			{/if}
		</dd>
	</div>
</div>
