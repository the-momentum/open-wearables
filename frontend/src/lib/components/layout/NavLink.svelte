<script lang="ts">
	import ExternalLink from '@lucide/svelte/icons/external-link';
	import BetaTag from '$lib/components/ui/BetaTag.svelte';
	import { ICON } from '$lib/components/ui/icon';
	import { cn } from '$lib/utils/cn';
	import type { NavItem } from '$lib/config/nav';
	import { NAV_ITEM, NAV_ITEM_ACTIVE, NAV_ITEM_IDLE } from './navItem';

	let {
		item,
		active = false,
		onnavigate
	}: {
		item: NavItem;
		active?: boolean;
		onnavigate?: () => void;
	} = $props();

	const Icon = $derived(item.icon);
</script>

<!-- Hrefs are pre-resolved in $lib/config/nav; the rule cannot see that. -->
<!-- eslint-disable svelte/no-navigation-without-resolve -->
<a
	href={item.href}
	target={item.external ? '_blank' : undefined}
	rel={item.external ? 'noreferrer' : undefined}
	aria-current={active ? 'page' : undefined}
	onclick={onnavigate}
	class={cn(NAV_ITEM, active ? NAV_ITEM_ACTIVE : NAV_ITEM_IDLE)}
>
	<Icon size={ICON.md} aria-hidden="true" class="shrink-0" />
	<span class="flex-1">{item.label}</span>
	{#if item.beta}<BetaTag />{/if}
	{#if item.external}
		<ExternalLink size={ICON.xs} aria-hidden="true" class="shrink-0 opacity-60" />
	{/if}
</a>
