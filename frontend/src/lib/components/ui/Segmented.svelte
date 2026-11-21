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
			<!-- The chosen segment stays a link but goes nowhere: its href can differ
			     from the current URL (an implicit default, a dropped cursor), and
			     following it would reload what is already on screen. A modified click
			     still opens it in a new tab. -->
			<a
				href={item.href}
				aria-current={active ? 'true' : undefined}
				data-sveltekit-noscroll
				onclick={(event) => {
					const plain = !(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey);
					if (active && plain && event.button === 0) event.preventDefault();
				}}
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
