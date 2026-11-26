<script lang="ts">
	import type { Component, Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';
	import { ICON } from './icon';
	import { CAPTION } from './typography';

	let {
		icon: Icon,
		class: className,
		children
	}: { icon?: Component; class?: string; children: Snippet } = $props();
</script>

<span class={cn('flex items-center gap-1.5', CAPTION, className)}>
	{#if Icon}
		<Icon size={ICON.xs} aria-hidden="true" class="shrink-0 text-muted-foreground/60" />
	{/if}
	{@render children()}
</span>
