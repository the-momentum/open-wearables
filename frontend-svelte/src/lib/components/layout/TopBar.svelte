<script lang="ts">
	import { page } from '$app/state';
	import { navLabelFor } from '$lib/config/nav';
	import Wordmark from './Wordmark.svelte';

	// Derived from the nav config rather than passed down per page, so a new
	// destination gets a title without touching every route.
	const sectionTitle = $derived(navLabelFor(page.url.pathname) ?? '');
</script>

<!-- Taller on mobile: the logotype stacks on two lines and needs the room. -->
<header
	class="sticky top-0 z-20 flex h-20 items-center border-b border-border bg-background/85 px-4
		backdrop-blur-md sm:px-6 lg:h-14"
>
	<Wordmark class="mx-auto h-12 lg:hidden" />

	<h1 class="hidden text-sm font-semibold tracking-tight lg:block">{sectionTitle}</h1>
</header>
