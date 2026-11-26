<script lang="ts">
	import { page } from '$app/state';
	import { navLabelFor } from '$lib/config/nav';
	import AccountAvatar from './AccountAvatar.svelte';
	import Wordmark from './Wordmark.svelte';

	// Derived from the nav config rather than passed down per page, so a new
	// destination gets a title without touching every route.
	const sectionTitle = $derived(navLabelFor(page.url.pathname) ?? '');
</script>

<!-- A phone has no sidebar, so the header carries the wordmark and whose account this is;
     the shadow does the border's job there and is too faint on a dark page. -->
<header
	class="sticky top-0 z-20 flex h-13 items-center justify-between bg-card px-4 shadow-header
		lg:h-14 lg:border-b lg:border-border lg:bg-card/85 lg:px-6 lg:shadow-none lg:backdrop-blur-md
		dark:border-b dark:border-border"
>
	<Wordmark class="h-9 lg:hidden" />
	{#if page.data.developer}
		<span class="lg:hidden"><AccountAvatar developer={page.data.developer} /></span>
	{/if}

	<h1 class="hidden text-sm font-medium lg:block">{sectionTitle}</h1>
</header>
