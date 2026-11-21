<script lang="ts">
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import type { DateValue } from '@internationalized/date';
	import { DatePicker, DateRangePicker, type Month } from 'bits-ui';
	import { CALENDAR } from './calendar';
	import { ICON } from './icon';

	// The single and the range picker share every part but the day, so one
	// layout serves both, handed the parts of whichever it sits in.
	let {
		parts,
		months,
		weekdays,
		dayClass
	}: {
		parts: typeof DatePicker | typeof DateRangePicker;
		months: Month<DateValue>[];
		weekdays: string[];
		dayClass: string;
	} = $props();
</script>

<parts.Header class={CALENDAR.header}>
	<parts.PrevButton class={CALENDAR.nav}>
		<ChevronLeft size={ICON.sm} aria-hidden="true" />
	</parts.PrevButton>
	<parts.Heading class={CALENDAR.heading} />
	<parts.NextButton class={CALENDAR.nav}>
		<ChevronRight size={ICON.sm} aria-hidden="true" />
	</parts.NextButton>
</parts.Header>

{#each months as month (month.value.toString())}
	<parts.Grid class={CALENDAR.grid}>
		<parts.GridHead>
			<parts.GridRow class="flex">
				{#each weekdays as day, i (i)}
					<parts.HeadCell class={CALENDAR.head}>{day}</parts.HeadCell>
				{/each}
			</parts.GridRow>
		</parts.GridHead>
		<parts.GridBody>
			{#each month.weeks as week (week[0].toString())}
				<parts.GridRow class="flex">
					{#each week as date (date.toString())}
						<parts.Cell {date} month={month.value} class="p-0">
							<parts.Day class={dayClass} />
						</parts.Cell>
					{/each}
				</parts.GridRow>
			{/each}
		</parts.GridBody>
	</parts.Grid>
{/each}
