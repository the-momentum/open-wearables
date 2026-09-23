<script lang="ts">
	import type { ProviderBrand } from '$lib/providers/labels';
	import { publicApiUrl } from '$lib/config/public-api';
	import ProviderMark from './ProviderMark.svelte';
	import { cn } from '$lib/utils/cn';

	let {
		provider,
		size = 'sm'
	}: {
		/** Whatever carries a logo — an OAuth catalogue entry or a settings row. */
		provider: ProviderBrand;
		size?: 'xs' | 'sm' | 'md' | 'lg';
	} = $props();

	// Static files on the API, so a browser can fetch them even though the
	// session cookie never goes there. Falls back if one 404s.
	let broken = $state(false);
	const base = publicApiUrl();
	const src = $derived(base && provider.icon_url ? `${base}${provider.icon_url}` : '');

	const TILE = {
		xs: 'size-5 rounded-md p-0.5',
		sm: 'size-10 p-1.5',
		md: 'size-12 p-2',
		lg: 'size-16 p-2.5'
	} as const;
	const MARK = { xs: 'sm', sm: 'md', md: 'md', lg: 'lg' } as const;
</script>

{#if src && !broken}
	<!-- A white square for every logo, as the old dashboard had: brand marks are
	     drawn for a light ground, and one shape per row is what makes roundels
	     and wordmarks read as one set. The ring is what shows it on a white card. -->
	<span
		class={cn(
			'grid shrink-0 place-items-center rounded-xl bg-white shadow-sm ring-1 ring-border',
			TILE[size]
		)}
	>
		<img {src} alt="" onerror={() => (broken = true)} class="size-full object-contain" />
	</span>
{:else}
	<ProviderMark provider={provider.provider} label={provider.name} size={MARK[size]} />
{/if}
