<script lang="ts">
	import { cn } from '$lib/utils/cn';

	let {
		label,
		value,
		share,
		shade = '',
		colour,
		size = 'sm'
	}: {
		label: string;
		value?: string;
		share?: string;
		/** The dot as a class (`bg-primary-soft`), or as a colour from a palette. */
		shade?: string;
		colour?: string;
		/** `md` beside a donut, `sm` under a bar. */
		size?: 'sm' | 'md';
	} = $props();

	const md = $derived(size === 'md');
</script>

<span class={cn('flex min-w-0 items-center', md ? 'gap-2.5 text-sm' : 'gap-2 text-xs')}>
	<span class="flex min-w-0 items-center gap-2">
		<span
			aria-hidden="true"
			class={cn('shrink-0 rounded-full', md ? 'size-2.5' : 'size-2', shade)}
			style:background={colour}
		></span>
		<span class="truncate text-foreground">{label}</span>
	</span>
	{#if value || share}
		<span class="flex shrink-0 items-center gap-1.5 text-muted-foreground tabular-nums">
			{#if value}<span>{value}</span>{/if}
			{#if share}<span>{share}</span>{/if}
		</span>
	{/if}
</span>
