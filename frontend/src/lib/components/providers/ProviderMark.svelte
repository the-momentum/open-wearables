<script lang="ts">
	import logo from '$lib/assets/logo.svg?raw';
	import { avatarTone } from '$lib/users/avatar';
	import { cn } from '$lib/utils/cn';

	let {
		provider,
		label,
		size = 'md'
	}: { provider: string; label: string; size?: 'sm' | 'md' | 'lg' } = $props();

	const SIZE = {
		sm: 'size-6 text-xs',
		md: 'size-9 text-xs',
		lg: 'size-16 rounded-xl text-base'
	} as const;

	// Open Wearables' own scores wear its mark: initials in a hashed tone could
	// land on a provider's colour, as OW and Oura both did.
	const own = $derived(provider === 'internal');
</script>

<!-- Letters where a logo would not fit, and what a logo falls back to when the
     API has none to serve. -->
<span
	aria-hidden="true"
	class={cn(
		'grid shrink-0 place-items-center rounded-lg font-medium',
		SIZE[size],
		own ? 'bg-inverted p-1 text-inverted-foreground [&>svg]:size-full' : avatarTone(provider)
	)}
>
	{#if own}
		<!-- eslint-disable-next-line svelte/no-at-html-tags -- build-time asset, never user input -->
		{@html logo}
	{:else}
		{label.slice(0, 2).toUpperCase()}
	{/if}
</span>
