<script lang="ts">
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import { slowNavigation } from '$lib/utils/navigation.svelte';
	import { isWithin } from '$lib/utils/url';
	import TabSkeleton from './TabSkeleton.svelte';

	let { within, children }: { within: string; children: Snippet } = $props();

	// A load holds the page until its data arrives; this shows the wait instead.
	const slow = slowNavigation();
	const inside = $derived(slow.target !== null && isWithin(slow.target.pathname, within));
	const switching = $derived(inside && slow.target?.pathname !== page.url.pathname);
	const refreshing = $derived(inside && !switching);
</script>

{#if switching}
	<TabSkeleton />
{:else}
	<!-- Stacks a tab's sections as the panel stacks the page's, so no tab needs a wrapper of its own. -->
	<div
		class="flex flex-col gap-4 transition-opacity duration-150 {refreshing
			? 'pointer-events-none opacity-60'
			: ''}"
		aria-busy={refreshing}
	>
		{@render children()}
	</div>
{/if}
