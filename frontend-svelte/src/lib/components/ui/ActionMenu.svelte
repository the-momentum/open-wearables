<script lang="ts">
	import type { Snippet } from 'svelte';
	import Ellipsis from '@lucide/svelte/icons/ellipsis';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import { cn } from '$lib/utils/cn';

	let {
		open = $bindable(false),
		label,
		title,
		class: className,
		children
	}: {
		open?: boolean;
		label: string;
		title: string;
		class?: string;
		/** Entries compose themselves — some are buttons, some submit a form. */
		children: Snippet;
	} = $props();
</script>

<button
	type="button"
	onclick={() => (open = true)}
	aria-label={label}
	aria-haspopup="dialog"
	aria-expanded={open}
	class={cn(
		'grid size-9 shrink-0 place-items-center rounded-lg border border-border text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground',
		className
	)}
>
	<Ellipsis size={16} aria-hidden="true" />
</button>

<Sheet bind:open {title}>
	<div class="flex flex-col gap-0.5 px-3 pb-2">
		{@render children()}
	</div>
</Sheet>
