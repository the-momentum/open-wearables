<script lang="ts">
	import { page } from '$app/state';
	import { navLabelFor } from '$lib/config/nav';
	import AppShell from '$lib/components/layout/AppShell.svelte';

	let { children } = $props();

	// Same source as the header, so a new destination gets a tab title for free.
	const title = $derived(navLabelFor(page.url.pathname));
</script>

<svelte:head>
	<title>{title ? `${title} · Open Wearables` : 'Open Wearables'}</title>
</svelte:head>

<AppShell>
	{@render children()}
</AppShell>
