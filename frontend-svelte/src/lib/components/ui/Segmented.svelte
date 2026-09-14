<script lang="ts">
	import { cn } from '$lib/utils/cn';

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

	const track = 'inline-flex rounded-lg bg-surface-muted p-0.5';
	const segment = (active: boolean) =>
		cn(
			'rounded-md px-2.5 py-1 text-xs font-medium whitespace-nowrap transition-colors',
			active
				? 'bg-surface text-foreground shadow-sm'
				: 'text-muted-foreground hover:text-foreground'
		);
</script>

<!-- Hrefs come from the caller, which resolves them. -->
<!-- eslint-disable svelte/no-navigation-without-resolve -->
<div class={track} role="group" aria-label={label}>
	{#each items as item (item.value)}
		{@const active = item.value === selected}
		{#if item.href}
			<a
				href={item.href}
				aria-current={active ? 'true' : undefined}
				data-sveltekit-noscroll
				class={segment(active)}
			>
				{item.label}
			</a>
		{:else}
			<button
				type="button"
				onclick={() => onselect?.(item.value)}
				aria-pressed={active}
				class={segment(active)}
			>
				{item.label}
			</button>
		{/if}
	{/each}
</div>
