<script lang="ts">
	import { page } from '$app/state';
	import TabStrip from '$lib/components/ui/TabStrip.svelte';
	import { activeTabSlug, tabsFor, userTabHref } from '$lib/users/tabs';
	import type { UserDetail } from '$lib/users/types';

	let { user }: { user: UserDetail } = $props();

	const tabs = $derived(
		tabsFor(user).map((tab) => ({
			href: userTabHref(user.id, tab.slug),
			label: tab.label,
			icon: tab.icon
		}))
	);

	const active = $derived(userTabHref(user.id, activeTabSlug(page.url.pathname, user.id)));
</script>

<TabStrip label="User sections" {tabs} {active} />
