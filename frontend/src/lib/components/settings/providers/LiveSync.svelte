<script lang="ts">
	import Timer from '@lucide/svelte/icons/timer';
	import Zap from '@lucide/svelte/icons/zap';
	import { enhance } from '$app/forms';
	import { SEGMENTS, segmentClass } from '$lib/components/ui/chip';
	import { ICON } from '$lib/components/ui/icon';
	import { cn } from '$lib/utils/cn';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';
	import { liveSyncLabel } from '$lib/settings/providers';
	import type { ProviderSetting } from '$lib/settings/types';

	let { provider }: { provider: ProviderSetting } = $props();

	const mode = $derived(provider.live_sync_mode ?? 'pull');
	const submit = createSubmitFlag();

	const MODES = [
		{ value: 'pull', label: 'Periodic pull', icon: Timer },
		{ value: 'webhook', label: 'Webhook', icon: Zap }
	] as const;
</script>

{#if provider.live_sync_configurable}
	<!-- Saves on the click, unlike the enable switches: this is one provider's
	     own setting, not a draft of the whole list. -->
	<form method="POST" action="?/liveSync" use:enhance={submit.enhance}>
		<input type="hidden" name="provider" value={provider.provider} />
		<div
			class="{SEGMENTS} gap-1 p-[3px]"
			role="group"
			aria-label="How {provider.name} reports new data"
		>
			{#each MODES as option (option.value)}
				{@const active = mode === option.value}
				<!-- The chosen one cannot be sent again: every switch reconciles the
				     provider's webhook subscriptions, and on pull that deletes all of them. -->
				<button
					type="submit"
					name="mode"
					value={option.value}
					disabled={submit.submitting || active}
					aria-pressed={active}
					class={cn(
						segmentClass(active),
						'disabled:cursor-default',
						// Dimmed while sending, not while disabled: the chosen mode is disabled
						// too, and it must not look switched off.
						submit.submitting && 'opacity-50'
					)}
				>
					<option.icon size={ICON.xs} aria-hidden="true" />
					{option.label}
				</button>
			{/each}
		</div>
	</form>
{:else}
	<span
		class="inline-flex items-center gap-2 self-start rounded-lg border border-border bg-surface px-3 py-2.5 text-xs font-medium text-foreground"
	>
		{#if mode === 'webhook'}
			<Zap size={ICON.xs} aria-hidden="true" />
		{:else}
			<Timer size={ICON.xs} aria-hidden="true" />
		{/if}
		{liveSyncLabel(mode)} only
	</span>
{/if}
