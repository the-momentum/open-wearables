<script lang="ts">
	import { page } from '$app/state';
	import TabStrip from '$lib/components/ui/TabStrip.svelte';
	import { activeTabSlug, USER_TABS, userTabHref } from '$lib/users/tabs';
	import type { User } from '$lib/users/types';

	let { user }: { user: User } = $props();

	const tabs = $derived(
		USER_TABS.map((tab) => ({
			href: userTabHref(user.id, tab.slug),
			label: tab.label,
			icon: tab.icon
		}))
	);

	const active = $derived(userTabHref(user.id, activeTabSlug(page.url.pathname, user.id)));
</script>

<TabStrip label="User sections" {tabs} {active} />
