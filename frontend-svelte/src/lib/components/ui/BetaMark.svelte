<script lang="ts">
	import { cn } from '$lib/utils/cn';

	/** Sits on an icon inside a `relative` wrapper, where there is no room for the word. */
	let { class: className }: { class?: string } = $props();
</script>

<span
	aria-hidden="true"
	class={cn(
		'absolute -top-1 -right-2 grid size-3.5 place-items-center rounded-full bg-surface',
		'text-[0.5rem] leading-none font-semibold text-primary ring-1 ring-primary/40',
		className
	)}
>
	β
</span>
