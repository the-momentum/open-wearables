<script lang="ts">
	import type { Component } from 'svelte';
	import BetaMark from './BetaMark.svelte';
	import BetaTag from './BetaTag.svelte';
	import ScrollFade from './ScrollFade.svelte';
	import { cn } from '$lib/utils/cn';

	export type Tab = {
		href: string;
		label: string;
		icon?: Component;
		/** Marks a section whose API is still moving under it. */
		beta?: boolean;
	};

	let {
		label,
		tabs,
		active
	}: {
		/** Names the strip for assistive tech. */
		label: string;
		tabs: Tab[];
		/** The href of the tab the reader is on. */
		active: string;
	} = $props();

	let scroller = $state<HTMLDivElement>();

	// A strip parked at the left would hide the tab you just opened.
	$effect(() => {
		void active;
		scroller
			?.querySelector('[aria-current="page"]')
			?.scrollIntoView({ block: 'nearest', inline: 'center' });
	});
</script>

<!-- Hrefs come from the caller, which resolves them. -->
<!-- eslint-disable svelte/no-navigation-without-resolve -->
<div class="-mx-4 sm:mx-0">
	<ScrollFade bind:scroller class="snap-x border-b border-border px-4 sm:px-0">
		<nav aria-label={label}>
			<ul class="flex gap-1">
				{#each tabs as tab (tab.href)}
					{@const current = tab.href === active}
					<li>
						<a
							href={tab.href}
							aria-current={current ? 'page' : undefined}
							class={cn(
								'-mb-px inline-flex snap-center items-center gap-2 border-b-2 px-3 py-2.5 text-sm whitespace-nowrap transition-colors',
								current
									? 'border-primary font-medium text-primary'
									: 'border-transparent text-muted-foreground hover:text-foreground'
							)}
						>
							{#if tab.icon}
								<!-- The word costs a tab's width on a phone, so below sm the mark
								     rides the icon instead — the same trade the bottom bar makes. -->
								<span class="relative {tab.beta ? 'mr-1 sm:mr-0' : ''}">
									<tab.icon size={15} aria-hidden="true" />
									{#if tab.beta}<BetaMark class="sm:hidden" />{/if}
								</span>
							{/if}
							{tab.label}
							{#if tab.beta}
								<span class="hidden sm:inline-flex"><BetaTag /></span>
								<span class="sr-only"> (beta)</span>
							{/if}
						</a>
					</li>
				{/each}
			</ul>
		</nav>
	</ScrollFade>
</div>
