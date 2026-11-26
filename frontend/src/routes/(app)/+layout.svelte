<script lang="ts">
	import { page } from '$app/state';
	import { pageTitle } from '$lib/branding/branding';
	import { navLabelFor } from '$lib/config/nav';
	import AppShell from '$lib/components/layout/AppShell.svelte';
	import NavigationProgress from '$lib/components/layout/NavigationProgress.svelte';

	let { children } = $props();

	// Same source as the header, so a new destination gets a tab title for free.
	const title = $derived(navLabelFor(page.url.pathname));
</script>

<svelte:head>
	<title>{pageTitle(page.data.brandName, title)}</title>
</svelte:head>

<NavigationProgress />

<AppShell>
	{@render children()}
</AppShell>
