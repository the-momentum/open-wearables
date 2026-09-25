<script lang="ts">
	import type { Snippet } from 'svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { cn } from '$lib/utils/cn';

	let {
		title,
		description,
		truncate = false,
		above,
		actions
	}: {
		title: string;
		description: string;
		/** For a description that is data, a URL say, rather than a sentence. */
		truncate?: boolean;
		above?: Snippet;
		actions?: Snippet;
	} = $props();
</script>

<div class="flex flex-wrap items-start justify-between gap-3">
	<div class="flex min-w-0 flex-col gap-0.5">
		{@render above?.()}
		<h1 class="text-lg font-semibold text-foreground">{title}</h1>
		<p class={cn(MICRO, truncate && 'truncate')}>{description}</p>
	</div>
	{@render actions?.()}
</div>
