<script lang="ts">
	import type { Component, Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';
	import { HEADING } from './typography';

	let {
		icon: Icon,
		title,
		description,
		action,
		class: className,
		bodyClass,
		children
	}: {
		/** Gives a section a mark of its own where several stack up. */
		icon?: Component;
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
			<div class="flex min-w-0 items-start gap-3">
				{#if Icon}
					<span
						aria-hidden="true"
						class="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"
					>
						<Icon size={16} />
					</span>
				{/if}
				<div class="min-w-0">
					<h2 id={headingId} class={HEADING}>{title}</h2>
					{#if description}
						<p class="mt-0.5 text-xs text-muted-foreground">{description}</p>
					{/if}
				</div>
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
