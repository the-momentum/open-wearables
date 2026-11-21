<script lang="ts">
	import { goto } from '$app/navigation';
	import DateField from '$lib/components/ui/DateField.svelte';
	import DateRangeField from '$lib/components/ui/DateRangeField.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import {
		ALL_TIME,
		RANGE_PRESETS,
		defaultRange,
		lastDays,
		matchingPreset,
		periodChanges,
		todayIso,
		type Period
	} from '$lib/filters/period';

	let {
		period,
		hrefFor
	}: { period: Period; hrefFor: (changes: Record<string, string | null>) => string } = $props();

	const today = todayIso();
	const preset = defaultRange();

	const items = $derived([
		{ value: 'all', label: 'All time', href: hrefFor(periodChanges(ALL_TIME)) },
		{
			value: 'day',
			label: 'Day',
			href: hrefFor(
				periodChanges({ mode: 'day', from: period.to ?? today, to: period.to ?? today })
			)
		},
		{ value: 'range', label: 'Range', href: hrefFor(periodChanges(preset)) }
	]);

	const presets = $derived(
		RANGE_PRESETS.map(({ label, days }) => ({
			value: label,
			label,
			href: hrefFor(periodChanges(lastDays(days)))
		}))
	);

	const box = 'h-9 w-full justify-center rounded-lg bg-surface px-2.5 text-xs sm:w-auto';

	function pick(changes: Record<string, string | null>) {
		// noScroll: changing a date must not throw the reader back to the header.
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- hrefFor resolves
		goto(hrefFor(changes), { noScroll: true });
	}
</script>

<div class="flex flex-wrap items-center gap-2">
	<Segmented label="Period" {items} selected={period.mode} />

	{#if period.mode === 'day'}
		<DateField
			label="Day"
			value={period.from ?? today}
			max={today}
			class={box}
			onchange={(day) => pick({ from: day, to: day })}
		/>
	{:else if period.mode === 'range'}
		<DateRangeField
			label="Date range"
			from={period.from ?? ''}
			to={period.to ?? today}
			max={today}
			class={box}
			onchange={(range) => pick(range)}
		/>
	{/if}

	{#if period.mode === 'range'}
		<Segmented label="Range preset" items={presets} selected={matchingPreset(period)} />
	{/if}
</div>
