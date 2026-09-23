<script lang="ts">
	import Timer from '@lucide/svelte/icons/timer';
	import Zap from '@lucide/svelte/icons/zap';
	import { enhance } from '$app/forms';
	import { cn } from '$lib/utils/cn';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';
	import { liveSyncLabel } from '$lib/settings/providers';
	import type { ProviderSetting } from '$lib/settings/types';

	let { provider }: { provider: ProviderSetting } = $props();

	const mode = $derived(provider.live_sync_mode ?? 'pull');
	const submit = createSubmitFlag();

	// The old dashboard's switcher: a light track, and the chosen mode a filled,
	// bordered pill — webhook in the accent, pull in neutral — so which one is on
	// reads from across the room rather than from a shadow.
	const MODES = [
		{
			value: 'pull',
			label: 'Periodic pull',
			icon: Timer,
			on: 'border-foreground/15 bg-foreground/10 text-foreground'
		},
		{
			value: 'webhook',
			label: 'Webhook',
			icon: Zap,
			on: 'border-primary/30 bg-primary/15 text-primary'
		}
	] as const;

	const FIXED = {
		pull: 'border-border bg-surface-muted text-muted-foreground',
		webhook: 'border-primary/20 bg-primary/10 text-primary'
	} as const;
</script>

{#if provider.live_sync_configurable}
	<!-- Saves on the click, unlike the enable switches: this is one provider's
	     own setting, not a draft of the whole list. -->
	<form method="POST" action="?/liveSync" use:enhance={submit.enhance}>
		<input type="hidden" name="provider" value={provider.provider} />
		<div
			class="inline-flex items-center gap-1 rounded-lg border border-border/60 bg-surface p-1"
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
						'inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-all duration-150 disabled:cursor-default',
						// Dimmed while sending, not while disabled: the chosen mode is disabled
						// too, and it must not look switched off.
						submit.submitting && 'opacity-50',
						active
							? `${option.on} shadow-sm`
							: 'border-border bg-surface text-foreground/75 hover:border-primary/40 hover:bg-primary/5 hover:text-primary'
					)}
				>
					<option.icon size={12} aria-hidden="true" />
					{option.label}
				</button>
			{/each}
		</div>
	</form>
{:else}
	<span
		class={cn(
			'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium',
			FIXED[mode]
		)}
	>
		{#if mode === 'webhook'}
			<Zap size={12} aria-hidden="true" />
		{:else}
			<Timer size={12} aria-hidden="true" />
		{/if}
		{liveSyncLabel(mode)} only
	</span>
{/if}
