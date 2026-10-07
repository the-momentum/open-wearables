<script lang="ts">
	import Ellipsis from '@lucide/svelte/icons/ellipsis';
	import { page } from '$app/state';
	import { PRIMARY_NAV_ITEMS, SECONDARY_NAV_ITEMS, isNavItemActive } from '$lib/config/nav';
	import BetaMark from '$lib/components/ui/BetaMark.svelte';
	import { TINY } from '$lib/components/ui/typography';
	import { cn } from '$lib/utils/cn';
	import MoreSheet from './MoreSheet.svelte';

	let sheetOpen = $state(false);

	const moreActive = $derived(
		SECONDARY_NAV_ITEMS.some((item) => isNavItemActive(item, page.url.pathname))
	);
</script>

<nav
	aria-label="Primary"
	class="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-surface/85
		pb-[env(safe-area-inset-bottom)] backdrop-blur-md lg:hidden"
>
	<!-- Follows the config; Tailwind cannot generate a class from a runtime value. -->
	<ul
		class="grid"
		style="grid-template-columns: repeat({PRIMARY_NAV_ITEMS.length + 1}, minmax(0, 1fr))"
	>
		{#each PRIMARY_NAV_ITEMS as item (item.href)}
			{@const active = isNavItemActive(item, page.url.pathname)}
			{@const Icon = item.icon}
			<li>
				<!-- eslint-disable svelte/no-navigation-without-resolve -->
				<a
					href={item.href}
					aria-current={active ? 'page' : undefined}
					class={cn(
						'flex min-h-14 flex-col items-center justify-center gap-1 font-medium transition-colors',
						TINY,
						active ? 'text-primary' : 'text-muted-foreground'
					)}
				>
					<!-- No room for the word on a phone, so the mark rides the icon. The
					     label says "beta" for anything that cannot see it. -->
					<span class="relative">
						<Icon size={20} aria-hidden="true" />
						{#if item.beta}<BetaMark />{/if}
					</span>
					{item.label}{#if item.beta}<span class="sr-only"> (beta)</span>{/if}
				</a>
			</li>
		{/each}

		<li>
			<button
				type="button"
				onclick={() => (sheetOpen = true)}
				aria-haspopup="dialog"
				aria-expanded={sheetOpen}
				class={cn(
					'flex min-h-14 w-full flex-col items-center justify-center gap-1 font-medium transition-colors',
					TINY,
					moreActive ? 'text-primary' : 'text-muted-foreground'
				)}
			>
				<Ellipsis size={20} aria-hidden="true" />
				More
			</button>
		</li>
	</ul>
</nav>

<MoreSheet bind:open={sheetOpen} />
