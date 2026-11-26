<script lang="ts">
	import type { Component, Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';
	import { ICON, ICON_TILE } from './icon';
	import { HEADING, TITLE } from './typography';

	let {
		icon: Icon,
		leading,
		title,
		description,
		action,
		stack = false,
		section = false,
		class: className,
		bodyClass,
		children
	}: {
		/** Gives a section a mark of its own where several stack up. */
		icon?: Component;
		/** In place of the icon, for a mark that is not one: a provider's logo. */
		leading?: Snippet;
		title?: string;
		description?: string;
		/** Rendered on the right of the header - a button, a count, a filter. */
		action?: Snippet;
		/** The action is a labelled button: on a phone it drops under the heading, full width. */
		stack?: boolean;
		/** A section of a tab: body-size title, the panel's corner. */
		section?: boolean;
		class?: string;
		bodyClass?: string;
		children: Snippet;
	} = $props();

	const headingId = $props.id();
	// A section or anything with a mark is titled at body size; a dashboard card at h6.
	const small = $derived(Boolean(Icon || leading || section));
</script>

<section
	aria-labelledby={title ? headingId : undefined}
	class={cn(
		'overflow-hidden rounded-lg border border-border bg-card',
		section && 'rounded-xl',
		className
	)}
>
	{#if title}
		<header
			class={cn(
				'flex items-start justify-between gap-3 border-b border-border p-4 sm:px-5 sm:py-3',
				stack && 'max-sm:flex-col max-sm:items-stretch'
			)}
		>
			<!-- A title alone sits level with its mark. -->
			<div class={cn('flex min-w-0 gap-3', description ? 'items-start' : 'items-center')}>
				{#if leading}
					{@render leading()}
				{:else if Icon}
					<span aria-hidden="true" class={cn(ICON_TILE, 'size-8')}>
						<Icon size={ICON.sm} />
					</span>
				{/if}
				<div class="flex min-w-0 flex-col gap-0.5">
					<h2 id={headingId} class={small ? HEADING : TITLE}>{title}</h2>
					{#if description}
						<p class="text-xs text-muted-foreground">{description}</p>
					{/if}
				</div>
			</div>
			{#if action}
				<div class={cn('shrink-0', stack && 'max-sm:*:w-full')}>{@render action()}</div>
			{/if}
		</header>
	{/if}

	<div class={cn('p-4 sm:p-5', bodyClass)}>
		{@render children()}
	</div>
</section>
