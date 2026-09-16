<script lang="ts">
	import { goto } from '$app/navigation';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import { defaultRange, todayIso, type Period } from '$lib/summary/period';

	let {
		period,
		hrefFor
	}: { period: Period; hrefFor: (changes: Record<string, string | null>) => string } = $props();

	const today = todayIso();
	const preset = defaultRange();

	const items = $derived([
		{ value: 'all', label: 'All time', href: hrefFor({ from: null, to: null }) },
		{
			value: 'day',
			label: 'Day',
			href: hrefFor({ from: period.to ?? today, to: period.to ?? today })
		},
		{ value: 'range', label: 'Range', href: hrefFor({ from: preset.from, to: preset.to }) }
	]);

	// Borderless inputs inside one bordered box, so the pair reads as one field.
	const field = 'h-7 bg-transparent px-2 text-xs tabular-nums text-foreground focus:outline-none';

	function pick(changes: Record<string, string | null>) {
		// noScroll: changing a date must not throw the reader back to the header.
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- hrefFor resolves
		goto(hrefFor(changes), { noScroll: true });
	}
</script>

<div class="flex flex-wrap items-center gap-2">
	<Segmented label="Period" {items} selected={period.mode} />

	{#if period.mode !== 'all'}
		<div class="inline-flex items-center rounded-lg border border-border bg-surface">
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
</div>
