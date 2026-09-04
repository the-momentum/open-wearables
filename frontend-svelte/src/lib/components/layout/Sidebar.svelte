<script lang="ts">
	import { page } from '$app/state';
	import { NAV_ITEMS, isNavItemActive } from '$lib/config/nav';
	import NavLink from './NavLink.svelte';
	import LogoutButton from './LogoutButton.svelte';
	import AppVersion from './AppVersion.svelte';
	import Wordmark from './Wordmark.svelte';
</script>

<!-- Desktop only; below lg the same destinations live in BottomNav. -->
<aside
	class="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-border bg-surface lg:flex"
>
	<div class="flex h-28 items-center justify-center border-b border-border/60 px-6">
		<Wordmark class="h-12" />
	</div>

	<nav aria-label="Main" class="flex-1 overflow-y-auto px-3 py-2">
		<ul class="flex flex-col gap-0.5">
			{#each NAV_ITEMS as item (item.href)}
				<li>
					<NavLink {item} active={isNavItemActive(item, page.url.pathname)} />
				</li>
			{/each}
		</ul>
	</nav>

	<div class="mx-3 border-t border-border/60"></div>

	<div class="p-3">
		<LogoutButton />
		<AppVersion />
	</div>
</aside>
