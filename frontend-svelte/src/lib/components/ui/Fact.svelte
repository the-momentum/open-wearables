<script lang="ts">
	import type { Snippet } from 'svelte';
	import { MICRO } from './typography';

	let { label, children }: { label: string; children: Snippet } = $props();
</script>

<!-- One label over one value, for a wrapping <dl> of them. -->
<div class="flex flex-col gap-0.5">
	<dt class={MICRO}>{label}</dt>
	<dd class="text-foreground/90 tabular-nums">{@render children()}</dd>
</div>
