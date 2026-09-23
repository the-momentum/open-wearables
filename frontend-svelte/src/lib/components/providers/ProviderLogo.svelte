<script lang="ts">
	import { publicApiUrl } from '$lib/config/public-api';
	import ProviderMark from './ProviderMark.svelte';
	import { cn } from '$lib/utils/cn';

	let {
		provider,
		size = 'md'
	}: {
		/** Whatever carries a logo — an OAuth catalogue entry or a settings row. */
		provider: { provider: string; name: string; icon_url: string };
		size?: 'sm' | 'md';
	} = $props();

	// The icons are static files on the API, so a browser can fetch them even
	// though the session cookie never goes there. Falls back if one 404s.
	let broken = $state(false);
	const base = publicApiUrl();
	const src = $derived(base && provider.icon_url ? `${base}${provider.icon_url}` : '');

	// Wider than tall: half these logos are wordmarks, and fitting POLAR or
	// WITHINGS into a square shrinks them to a smudge next to Garmin's roundel.
	const SIZE = { sm: 'h-7 w-10 p-0.5', md: 'h-10 w-13 p-1' } as const;
</script>

{#if src && !broken}
	<img
		{src}
		alt=""
		onerror={() => (broken = true)}
		class={cn('shrink-0 rounded-lg bg-white object-contain', SIZE[size])}
	/>
{:else}
	<ProviderMark provider={provider.provider} label={provider.name} {size} />
{/if}
