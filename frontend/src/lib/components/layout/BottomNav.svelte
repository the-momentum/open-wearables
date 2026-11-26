<script lang="ts">
	import Ellipsis from '@lucide/svelte/icons/ellipsis';
	import { page } from '$app/state';
	import { PRIMARY_NAV_ITEMS, SECONDARY_NAV_ITEMS, isNavItemActive } from '$lib/config/nav';
	import BetaMark from '$lib/components/ui/BetaMark.svelte';
	import { ICON } from '$lib/components/ui/icon';
	import { TINY } from '$lib/components/ui/typography';
	import { cn } from '$lib/utils/cn';
	import MoreSheet from './MoreSheet.svelte';

	let sheetOpen = $state(false);

	const ITEM = `flex h-12.5 w-full flex-col items-center justify-center gap-0.5 font-medium transition-colors ${TINY}`;

	// Lit while its sheet is open too.
	const moreActive = $derived(
		sheetOpen || SECONDARY_NAV_ITEMS.some((item) => isNavItemActive(item, page.url.pathname))
	);
</script>

<nav
	aria-label="Primary"
	class="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-card px-2 pt-1
		pb-[env(safe-area-inset-bottom)] lg:hidden"
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
					class={cn(ITEM, active ? 'text-primary' : 'text-muted-foreground')}
				>
					<!-- No room for the word on a phone, so the mark rides the icon. The
					     label says "beta" for anything that cannot see it. -->
					<span class="grid h-6.5 w-8 place-items-center">
						<span class="relative">
							<Icon size={ICON.md} aria-hidden="true" />
							{#if item.beta}<BetaMark />{/if}
						</span>
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
				class={cn(ITEM, moreActive ? 'text-primary' : 'text-muted-foreground')}
			>
				<span class="grid h-6.5 w-8 place-items-center">
					<Ellipsis size={ICON.md} aria-hidden="true" />
				</span>
				More
			</button>
		</li>
	</ul>
</nav>

<MoreSheet bind:open={sheetOpen} />
