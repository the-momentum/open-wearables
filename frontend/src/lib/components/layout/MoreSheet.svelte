<script lang="ts">
	import { page } from '$app/state';
	import { SECONDARY_NAV_ITEMS, isNavItemActive } from '$lib/config/nav';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import AccountFooter from './AccountFooter.svelte';
	import NavLink from './NavLink.svelte';

	let { open = $bindable(false) }: { open?: boolean } = $props();
</script>

<Sheet bind:open title="More">
	<nav aria-label="Secondary" class="overflow-y-auto px-3 pb-2">
		<ul class="flex flex-col gap-0.5">
			{#each SECONDARY_NAV_ITEMS as item (item.href)}
				<li>
					<NavLink
						{item}
						active={isNavItemActive(item, page.url.pathname)}
						onnavigate={() => (open = false)}
					/>
				</li>
			{/each}
		</ul>
	</nav>

	<!-- The sidebar is desktop-only, so this is the only way out on a phone. -->
	<AccountFooter class="px-3 pt-3" />
</Sheet>
