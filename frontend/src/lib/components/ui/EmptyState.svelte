<script lang="ts">
	import type { Component, Snippet } from 'svelte';
	import { ICON } from './icon';
	import { MICRO } from './typography';

	let {
		icon: Icon,
		title,
		description,
		children
	}: { icon?: Component; title: string; description?: string; children?: Snippet } = $props();
</script>

<div class="flex flex-col items-center gap-2 px-4 py-10 text-center">
	{#if Icon}
		<Icon size={ICON.md} aria-hidden="true" class="text-muted-foreground" />
	{/if}
	<p class="text-sm font-medium text-secondary-foreground">{title}</p>
	{#if description}
		<p class="max-w-sm {MICRO}">{description}</p>
	{/if}
	{#if children}
		<div class="mt-2">{@render children()}</div>
	{/if}
</div>
