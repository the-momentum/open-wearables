<script lang="ts">
	import { page } from '$app/state';
	import { SECONDARY_NAV_ITEMS, isNavItemActive } from '$lib/config/nav';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import NavLink from './NavLink.svelte';
	import LogoutButton from './LogoutButton.svelte';
	import AppVersion from './AppVersion.svelte';

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
	<div class="mx-3 mt-1 border-t border-border/60"></div>
	<div class="px-3 pt-2">
		<LogoutButton />
		<AppVersion />
	</div>
</Sheet>
