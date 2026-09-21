<script lang="ts">
	import type { Component } from 'svelte';
	import { MICRO } from './typography';

	export type Figure = { icon: Component; label: string; value: string | number };

	let { figures, label }: { figures: Figure[]; label: string } = $props();

	// Spelled out, because Tailwind reads these class names out of the source and
	// never sees one that was assembled at runtime.
	const COLUMNS: Record<number, string> = {
		2: 'sm:grid-cols-2',
		3: 'sm:grid-cols-3',
		4: 'sm:grid-cols-4'
	};
</script>

<!-- No frame: the icon chip is what ties a number to its label, and a bordered
     tile only added a box inside whatever box the caller already had. -->
<dl
	aria-label={label}
	class="grid grid-cols-2 gap-x-4 gap-y-4 {COLUMNS[figures.length] ?? 'sm:grid-cols-4'}"
>
	{#each figures as figure (figure.label)}
		<div class="flex items-center gap-3">
			<span
				aria-hidden="true"
				class="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"
			>
				<figure.icon size={17} />
			</span>
			<div class="min-w-0">
				<dd class="truncate text-lg font-semibold text-foreground tabular-nums sm:text-xl">
					{figure.value}
				</dd>
				<dt class="truncate {MICRO}">{figure.label}</dt>
			</div>
		</div>
	{/each}
</dl>
