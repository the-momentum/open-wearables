<script lang="ts">
	import { SEGMENTS, segmentClass } from './chip';

	type Segment = { value: string; label: string; href?: string };

	let {
		label,
		items,
		selected,
		onselect
	}: {
		/** Names the group for assistive tech; the visible caption is the caller's. */
		label: string;
		items: Segment[];
		selected: string;
		onselect?: (value: string) => void;
	} = $props();
</script>

<!-- Hrefs come from the caller, which resolves them. -->
<!-- eslint-disable svelte/no-navigation-without-resolve -->
<div class="{SEGMENTS} p-0.5" role="group" aria-label={label}>
	{#each items as item (item.value)}
		{@const active = item.value === selected}
		{#if item.href}
			<a
				href={item.href}
				aria-current={active ? 'true' : undefined}
				data-sveltekit-noscroll
				class={segmentClass(active)}
			>
				{item.label}
			</a>
		{:else}
			<button
				type="button"
				onclick={() => onselect?.(item.value)}
				aria-pressed={active}
				class={segmentClass(active)}
			>
				{item.label}
			</button>
		{/if}
	{/each}
</div>
