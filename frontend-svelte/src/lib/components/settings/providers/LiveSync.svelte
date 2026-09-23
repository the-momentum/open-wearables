<script lang="ts">
	import Timer from '@lucide/svelte/icons/timer';
	import Zap from '@lucide/svelte/icons/zap';
	import { enhance } from '$app/forms';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';
	import { liveSyncLabel } from '$lib/settings/providers';
	import type { ProviderSetting } from '$lib/settings/types';

	let { provider }: { provider: ProviderSetting } = $props();

	const mode = $derived(provider.live_sync_mode ?? 'pull');
	const submit = createSubmitFlag();

	const MODES = [
		{ value: 'pull', label: 'Periodic pull', icon: Timer, on: 'bg-surface text-foreground' },
		{ value: 'webhook', label: 'Webhook', icon: Zap, on: 'bg-primary/12 text-primary' }
	] as const;

	const SEGMENT =
		'inline-flex min-h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium whitespace-nowrap transition-colors disabled:opacity-50';
</script>

{#if provider.live_sync_configurable}
	<!-- Saves on the click, unlike the enable switches: this is one provider's
	     own setting, not a draft of the whole list. -->
	<form method="POST" action="?/liveSync" use:enhance={submit.enhance}>
		<div
			class="inline-flex gap-0.5 rounded-lg bg-surface-muted p-0.5 ring-1 ring-border/60"
			role="group"
			aria-label="How {provider.name} reports new data"
		>
			{#each MODES as option (option.value)}
				{@const active = mode === option.value}
				<button
					type="submit"
					name="mode"
					value={option.value}
					disabled={submit.submitting}
					aria-pressed={active}
					class="{SEGMENT} {active
						? `${option.on} shadow-sm`
						: 'text-muted-foreground hover:text-foreground'}"
				>
					<option.icon size={13} aria-hidden="true" />
					{option.label}
				</button>
			{/each}
		</div>
		<input type="hidden" name="provider" value={provider.provider} />
	</form>
{:else}
	<!-- Not a choice this provider offers: how it reports new data is fixed, so
	     it reads as a fact rather than a control nobody can move. -->
	<span
		class="inline-flex min-h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-medium
			{mode === 'webhook' ? 'bg-primary/10 text-primary' : 'bg-surface-muted text-muted-foreground'}"
	>
		{#if mode === 'webhook'}
			<Zap size={13} aria-hidden="true" />
		{:else}
			<Timer size={13} aria-hidden="true" />
		{/if}
		{liveSyncLabel(mode)} only
	</span>
{/if}
