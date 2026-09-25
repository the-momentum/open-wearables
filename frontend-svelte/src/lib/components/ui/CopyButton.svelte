<script lang="ts">
	import Check from '@lucide/svelte/icons/check';
	import Copy from '@lucide/svelte/icons/copy';
	import { createCopier } from '$lib/utils/clipboard.svelte';
	import { cn } from '$lib/utils/cn';

	let {
		value,
		label,
		icon: Icon = Copy,
		place = 'inline',
		class: className
	}: {
		value: string;
		/** What is being copied, for the button's accessible name. */
		label: string;
		/** Where the value is, when a clipboard glyph would not say it. */
		icon?: typeof Copy;
		/** Named for where it sits, because that is what decides the shape. */
		place?: 'inline' | 'field' | 'action';
		class?: string;
	} = $props();

	const copier = createCopier();

	const PLACE = {
		inline: 'size-7 rounded',
		field: 'size-11 rounded-lg border border-border hover:bg-surface-muted',
		action: 'min-h-8 px-2.5 rounded-lg border border-border hover:bg-surface-muted'
	} as const;
</script>

<button
	type="button"
	onclick={() => copier.copy(value)}
	aria-label={copier.copied ? `${label} copied` : `Copy ${label}`}
	class={cn(
		'grid shrink-0 place-items-center text-muted-foreground transition-colors hover:text-foreground',
		PLACE[place],
		className
	)}
>
	{#if copier.copied}
		<Check size={place === 'field' ? 16 : 13} aria-hidden="true" class="text-success" />
	{:else}
		<Icon size={place === 'field' ? 16 : 13} aria-hidden="true" />
	{/if}
</button>
