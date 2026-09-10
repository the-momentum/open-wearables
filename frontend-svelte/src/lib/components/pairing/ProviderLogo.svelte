<script lang="ts">
	import { publicApiUrl } from '$lib/config/public-api';
	import ProviderMark from '$lib/components/providers/ProviderMark.svelte';
	import type { Provider } from '$lib/server/providers';

	let { provider }: { provider: Provider } = $props();

	// Public page, so the browser can fetch the real logo. Falls back if it 404s.
	let broken = $state(false);
	const base = publicApiUrl();
	const src = $derived(base && provider.icon_url ? `${base}${provider.icon_url}` : '');
</script>

{#if src && !broken}
	<img
		{src}
		alt=""
		onerror={() => (broken = true)}
		class="size-10 rounded-lg bg-white object-contain p-1.5"
	/>
{:else}
	<ProviderMark provider={provider.provider} label={provider.name} />
{/if}
