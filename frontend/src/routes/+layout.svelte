<script lang="ts">
	import '../app.css';
	import { asset } from '$app/paths';
	import { page } from '$app/state';
	import { setLucideProps } from '@lucide/svelte';

	// The design's icons are 1px on screen at every size.
	setLucideProps({ strokeWidth: 1, absoluteStrokeWidth: true });

	let { children } = $props();
</script>

<svelte:head>
	<title>{page.data.brandName}</title>
	{#if page.data.faviconUrl}
		<link rel="icon" href={page.data.faviconUrl} />
	{:else}
		<!-- Fallback for browsers that ignore the media-scoped icons below. -->
		<link rel="icon" href={asset('/favicon.ico')} sizes="any" />
		{#each ['light', 'dark'] as scheme (scheme)}
			{#each [32, 16] as size (size)}
				<link
					rel="icon"
					type="image/png"
					sizes="{size}x{size}"
					href={asset(`/favicon-${scheme}-${size}x${size}.png`)}
					media="(prefers-color-scheme: {scheme})"
				/>
			{/each}
		{/each}
	{/if}
</svelte:head>

{@render children()}
