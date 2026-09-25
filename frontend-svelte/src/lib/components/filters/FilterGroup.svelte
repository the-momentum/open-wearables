<script lang="ts">
	import type { Snippet } from 'svelte';
	import Caption from '$lib/components/ui/Caption.svelte';

	let { label, children }: { label: string; children: Snippet } = $props();
</script>

<div class="flex flex-col gap-1.5">
	<Caption>{label}</Caption>
	{@render children()}
</div>
