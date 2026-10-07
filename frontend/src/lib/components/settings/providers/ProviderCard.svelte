<script lang="ts">
	import ProviderLogo from '$lib/components/providers/ProviderLogo.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Switch from '$lib/components/ui/Switch.svelte';
	import { TINY } from '$lib/components/ui/typography';
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

<li class="flex flex-col gap-3 rounded-lg border border-border p-4">
	<div class="flex items-start gap-3">
		<ProviderLogo {provider} size="lg" />

		<div class="flex min-w-0 flex-1 flex-col items-start gap-1.5">
			<span class="max-w-full truncate text-sm font-medium text-foreground">{provider.name}</span>
			<div class="flex flex-wrap items-center gap-x-2 gap-y-1">
				<!-- What the server holds; the switch is the draft, and the note
				     says when the two disagree. -->
				<Badge tone={provider.is_enabled ? 'success' : 'neutral'}>
					{provider.is_enabled ? 'Enabled' : 'Disabled'}
				</Badge>
				{#if changed}
					<span class="{TINY} text-primary">
						{enabled ? 'will be enabled' : 'will be disabled'}
					</span>
				{/if}
			</div>
		</div>

		<Switch checked={enabled} label="Enable {provider.name}" onchange={ontoggle} />
	</div>

	<!-- Full width under the header: beside the logo, a third of a desktop row
	     is too narrow for both pills. -->
	<div class="border-t border-border/60 pt-3">
		<LiveSync {provider} />
	</div>
</li>
