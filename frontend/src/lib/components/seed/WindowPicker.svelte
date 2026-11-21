<script lang="ts">
	import DateRangeField from '$lib/components/ui/DateRangeField.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import { FIELD } from '$lib/components/ui/field';
	import { MICRO } from '$lib/components/ui/typography';
	import { datesFor, WINDOW_MONTHS, type Window } from '$lib/seed/draft';

	let { value = $bindable({ months: 6 }) }: { value?: Window } = $props();

	const selected = $derived('months' in value ? String(value.months) : 'custom');

	const items = [
		...WINDOW_MONTHS.map((months) => ({ value: String(months), label: `${months} mo` })),
		{ value: 'custom', label: 'Dates' }
	];

	// Switching to dates starts from what the months meant, so the range is
	// something to adjust rather than two blanks to fill.
	function pick(choice: string) {
		if (choice !== 'custom') {
			value = { months: Number(choice) };
			return;
		}
		if ('months' in value) value = datesFor(value.months);
	}

	const DATE = `${FIELD} w-auto px-3`;
</script>

<div class="flex flex-col gap-1.5">
	<span class={MICRO}>Data spans</span>
	<div class="flex flex-wrap items-center gap-2">
		<Segmented label="Data spans" {items} {selected} onselect={pick} />
		{#if !('months' in value)}
			<DateRangeField
				label="Date range"
				from={value.from}
				to={value.to}
				class={DATE}
				onchange={(range) => (value = range)}
			/>
		{/if}
	</div>
</div>
