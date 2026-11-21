<script lang="ts">
	import { goto } from '$app/navigation';
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

	// Borderless inputs inside one bordered box, so the pair reads as one field.
	const field =
		'bg-transparent text-xs text-foreground tabular-nums focus:outline-none [&::-webkit-calendar-picker-indicator]:cursor-pointer [&::-webkit-calendar-picker-indicator]:opacity-50';

	function pick(changes: Record<string, string | null>) {
		// noScroll: changing a date must not throw the reader back to the header.
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- hrefFor resolves
		goto(hrefFor(changes), { noScroll: true });
	}
</script>

<div class="flex flex-wrap items-center gap-2">
	<Segmented label="Period" {items} selected={period.mode} />

	{#if period.mode !== 'all'}
		<div
			class="flex h-9 w-full items-center justify-center gap-2 rounded-lg border border-border bg-surface px-2.5 focus-within:outline-2 focus-within:outline-offset-2
				focus-within:outline-ring sm:inline-flex sm:w-auto"
		>
			<label class="sr-only" for="period-from">{period.mode === 'day' ? 'Day' : 'From'}</label>
			<input
				id="period-from"
				type="date"
				value={period.from}
				max={period.mode === 'day' ? today : (period.to ?? today)}
				class={field}
				onchange={(event) =>
					pick(
						period.mode === 'day'
							? { from: event.currentTarget.value, to: event.currentTarget.value }
							: { from: event.currentTarget.value }
					)}
			/>

			{#if period.mode === 'range'}
				<span class="text-xs text-muted-foreground">–</span>
				<label class="sr-only" for="period-to">To</label>
				<input
					id="period-to"
					type="date"
					value={period.to}
					min={period.from ?? undefined}
					max={today}
					class={field}
					onchange={(event) => pick({ to: event.currentTarget.value })}
				/>
			{/if}
		</div>
	{/if}

	{#if period.mode === 'range'}
		<Segmented label="Range preset" items={presets} selected={matchingPreset(period)} />
	{/if}
</div>
