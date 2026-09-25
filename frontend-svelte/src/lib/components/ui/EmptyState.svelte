<script lang="ts">
	import type { Component, Snippet } from 'svelte';

	let {
		icon: Icon,
		title,
		description,
		children
	}: { icon?: Component; title: string; description?: string; children?: Snippet } = $props();
</script>

<div class="flex flex-col items-center gap-2 px-4 py-10 text-center">
	{#if Icon}
		<Icon size={22} aria-hidden="true" class="text-muted-foreground/50" />
	{/if}
	<p class="text-sm font-medium text-foreground/80">{title}</p>
	{#if description}
		<p class="max-w-sm text-xs text-muted-foreground">{description}</p>
	{/if}
	{#if children}
		<div class="mt-2">{@render children()}</div>
	{/if}
</div>
