<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';

	let {
		title,
		description,
		action,
		class: className,
		bodyClass,
		children
	}: {
		title?: string;
		description?: string;
		/** Rendered on the right of the header — a button, a count, a filter. */
		action?: Snippet;
		class?: string;
		bodyClass?: string;
		children: Snippet;
	} = $props();

	const headingId = $props.id();
</script>

<section
	aria-labelledby={title ? headingId : undefined}
	class={cn('overflow-hidden rounded-xl border border-border bg-surface', className)}
>
	{#if title}
		<header class="flex items-start justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
			<div class="min-w-0">
				<h2 id={headingId} class="text-sm font-semibold text-foreground">{title}</h2>
				{#if description}
					<p class="mt-0.5 text-xs text-muted-foreground">{description}</p>
				{/if}
			</div>
			{#if action}
				<div class="shrink-0">{@render action()}</div>
			{/if}
		</header>
	{/if}

	<div class={cn('p-4 sm:p-5', bodyClass)}>
		{@render children()}
	</div>
</section>
