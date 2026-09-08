<script lang="ts">
	import { page } from '$app/state';
	import { cn } from '$lib/utils/cn';
	import { activeTabSlug, tabsFor, userTabHref } from '$lib/users/tabs';
	import type { UserDetail } from '$lib/users/types';

	let { user }: { user: UserDetail } = $props();

	const tabs = $derived(tabsFor(user));
	const active = $derived(activeTabSlug(page.url.pathname, user.id));

	let scroller = $state<HTMLDivElement>();
	// Both true on a desktop, where everything fits, so the fades hide themselves.
	let atStart = $state(true);
	let atEnd = $state(true);

	function track() {
		if (!scroller) return;
		atStart = scroller.scrollLeft <= 1;
		atEnd = scroller.scrollLeft + scroller.clientWidth >= scroller.scrollWidth - 1;
	}

	// A strip parked at the left would hide the tab you just opened.
	$effect(() => {
		void active;
		scroller?.querySelector('[aria-current="page"]')?.scrollIntoView({
			block: 'nearest',
			inline: 'center'
		});
		track();
	});
</script>

<svelte:window onresize={track} />

<!-- Hrefs come from userTabHref, which resolves them. -->
<!-- eslint-disable svelte/no-navigation-without-resolve -->
<div class="relative -mx-4 sm:mx-0">
	<div
		bind:this={scroller}
		onscroll={track}
		class="scroller flex snap-x overflow-x-auto border-b border-border px-4 sm:px-0"
	>
		<nav aria-label="User sections">
			<ul class="flex gap-1">
				{#each tabs as tab (tab.slug)}
					<li>
						<a
							href={userTabHref(user.id, tab.slug)}
							aria-current={tab.slug === active ? 'page' : undefined}
							class={cn(
								'-mb-px inline-flex snap-center items-center gap-2 border-b-2 px-3 py-2.5 text-sm whitespace-nowrap transition-colors',
								tab.slug === active
									? 'border-primary font-medium text-primary'
									: 'border-transparent text-muted-foreground hover:text-foreground'
							)}
						>
							<tab.icon size={15} aria-hidden="true" />
							{tab.label}
						</a>
					</li>
				{/each}
			</ul>
		</nav>
	</div>

	<!-- Stops a pixel short of the rule so the rule stays whole. -->
	{#if !atStart}
		<div
			aria-hidden="true"
			class="pointer-events-none absolute top-0 bottom-px left-0 w-8 bg-gradient-to-r from-background to-transparent"
		></div>
	{/if}
	{#if !atEnd}
		<div
			aria-hidden="true"
			class="pointer-events-none absolute top-0 right-0 bottom-px w-8 bg-gradient-to-l from-background to-transparent"
		></div>
	{/if}
</div>

<style>
	/* No utility for this in Tailwind v4, and the bar would sit on the rule. */
	.scroller {
		scrollbar-width: none;
	}

	.scroller::-webkit-scrollbar {
		display: none;
	}
</style>
