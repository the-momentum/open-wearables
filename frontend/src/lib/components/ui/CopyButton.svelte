<script lang="ts">
	import Check from '@lucide/svelte/icons/check';
	import Copy from '@lucide/svelte/icons/copy';
	import { createCopier } from '$lib/utils/clipboard.svelte';
	import { cn } from '$lib/utils/cn';
	import { buttonClass, ICON_BUTTON } from './button';
	import { ICON } from './icon';

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
		inline:
			'grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:text-secondary-foreground',
		field: buttonClass('outline'),
		action: ICON_BUTTON
	} as const;

	const size = $derived(place === 'inline' ? ICON.xs : ICON.sm);
</script>

<button
	type="button"
	onclick={() => copier.copy(value)}
	aria-label={copier.copied ? `${label} copied` : `Copy ${label}`}
	class={cn(PLACE[place], className)}
>
	{#if copier.copied}
		<Check {size} aria-hidden="true" class="text-success" />
	{:else}
		<Icon {size} aria-hidden="true" />
	{/if}
</button>
