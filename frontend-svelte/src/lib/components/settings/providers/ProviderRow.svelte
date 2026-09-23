<script lang="ts">
	import ProviderLogo from '$lib/components/providers/ProviderLogo.svelte';
	import Switch from '$lib/components/ui/Switch.svelte';
	import { MICRO, TINY } from '$lib/components/ui/typography';
	import LiveSync from './LiveSync.svelte';
	import type { ProviderSetting } from '$lib/settings/types';

	let {
		provider,
		enabled,
		ontoggle
	}: {
		provider: ProviderSetting;
		/** The draft state, which is not yet what the server holds. */
		enabled: boolean;
		ontoggle: (next: boolean) => void;
	} = $props();

	const changed = $derived(enabled !== provider.is_enabled);
</script>

<div class="flex items-center gap-3 py-3.5 sm:gap-4">
	<!-- Dimmed rather than badged: a disabled provider should read as off at a
	     glance, down the whole column, without a word per row saying so. -->
	<div
		class="flex min-w-0 flex-1 items-center gap-3 transition-opacity sm:gap-4"
		class:opacity-45={!enabled}
	>
		<ProviderLogo {provider} />

		<div class="flex min-w-0 flex-col items-start gap-1.5">
			<div class="flex flex-wrap items-center gap-2">
				<span class="truncate text-sm font-medium text-foreground">{provider.name}</span>
				{#if changed}
					<span class="{TINY} text-primary">
						{enabled ? 'will be enabled' : 'will be disabled'}
					</span>
				{:else if !enabled}
					<span class={MICRO}>disabled</span>
				{/if}
			</div>

			<LiveSync {provider} />
		</div>
	</div>

	<Switch checked={enabled} label="Enable {provider.name}" onchange={ontoggle} />
</div>
