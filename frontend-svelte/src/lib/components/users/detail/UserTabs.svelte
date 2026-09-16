<script lang="ts">
	import { page } from '$app/state';
	import ScrollFade from '$lib/components/ui/ScrollFade.svelte';
	import { cn } from '$lib/utils/cn';
	import { activeTabSlug, tabsFor, userTabHref } from '$lib/users/tabs';
	import type { UserDetail } from '$lib/users/types';

	let { user }: { user: UserDetail } = $props();

	const tabs = $derived(tabsFor(user));
	const active = $derived(activeTabSlug(page.url.pathname, user.id));

	let scroller = $state<HTMLDivElement>();

	// A strip parked at the left would hide the tab you just opened.
	$effect(() => {
		void active;
		scroller
			?.querySelector('[aria-current="page"]')
			?.scrollIntoView({ block: 'nearest', inline: 'center' });
	});
</script>

<!-- Hrefs come from userTabHref, which resolves them. -->
<!-- eslint-disable svelte/no-navigation-without-resolve -->
<div class="-mx-4 sm:mx-0">
	<ScrollFade bind:scroller class="snap-x border-b border-border px-4 sm:px-0">
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
	</ScrollFade>
</div>
