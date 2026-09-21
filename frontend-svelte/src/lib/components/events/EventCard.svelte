<script lang="ts">
	import type { Component, Snippet } from 'svelte';
	import ProviderMark from '$lib/components/providers/ProviderMark.svelte';
	import { deviceIcon } from '$lib/providers/devices';
	import type { WorkoutSource } from '$lib/workouts/types';
	import AccordionCard from './AccordionCard.svelte';

	let {
		icon,
		source,
		providerLabel,
		title,
		when,
		metrics,
		details
	}: {
		icon: Component;
		source: WorkoutSource;
		providerLabel: string;
		title: Snippet;
		when: Snippet;
		metrics: Snippet;
		details: Snippet;
	} = $props();

	// The device is the useful half when one provider carries several: "Garmin"
	// twice tells an admin nothing, "Forerunner 265" tells them which watch.
	const device = $derived(source.device_name ?? source.device);
	const origin = $derived([providerLabel, device].filter(Boolean).join(' · '));
	const DeviceIcon = $derived(deviceIcon(source.device_type));
</script>

<!-- One record from one device, which is every card but a score's: those are a
     day of one measure from whoever scored it, and name no device at all. -->
<AccordionCard {icon} {title} {when} {metrics} {details}>
	{#snippet aside()}
		<!-- Narrow screens keep the mark and drop the words; the title holds them.
		     The icon belongs to the device, not the provider, and comes from
		     `device_type` — a ring must not be drawn as a watch. -->
		<span class="flex shrink-0 items-center gap-1.5" title={origin}>
			<ProviderMark provider={source.provider} label={providerLabel} size="sm" />
			<span class="hidden items-center gap-1 text-xs text-muted-foreground sm:inline-flex">
				{providerLabel}
				{#if device}
					<span aria-hidden="true" class="text-muted-foreground/40">·</span>
					<DeviceIcon size={12} aria-hidden="true" class="shrink-0 text-muted-foreground/60" />
					{device}
				{/if}
			</span>
		</span>
	{/snippet}
</AccordionCard>
