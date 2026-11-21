<script lang="ts">
	import type { Snippet } from 'svelte';
	import Ellipsis from '@lucide/svelte/icons/ellipsis';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import { cn } from '$lib/utils/cn';
	import { buttonClass, ICON_BUTTON } from './button';
	import { ICON } from './icon';

	let {
		open = $bindable(false),
		label,
		title,
		quiet = false,
		class: className,
		children
	}: {
		open?: boolean;
		label: string;
		title: string;
		/** A bare glyph, for a corner of a card; bordered, it sits in a row of buttons. */
		quiet?: boolean;
		class?: string;
		/** Entries compose themselves - some are buttons, some submit a form. */
		children: Snippet;
	} = $props();
</script>

<button
	type="button"
	onclick={() => (open = true)}
	aria-label={label}
	aria-haspopup="dialog"
	aria-expanded={open}
	class={cn(quiet ? ICON_BUTTON : buttonClass('outline', 'md', 'shrink-0'), className)}
>
	<Ellipsis size={ICON.sm} aria-hidden="true" />
</button>

<Sheet bind:open {title}>
	<div class="flex flex-col gap-2 px-4 pt-1 pb-2 sm:flex-row sm:flex-wrap">
		{@render children()}
	</div>
</Sheet>
