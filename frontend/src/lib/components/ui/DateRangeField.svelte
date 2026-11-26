<script lang="ts">
	import CalendarIcon from '@lucide/svelte/icons/calendar';
	import { DateRangePicker, Portal } from 'bits-ui';
	import { cn } from '$lib/utils/cn';
	import { finePointer } from '$lib/utils/pointer';
	import CalendarMonths from './CalendarMonths.svelte';
	import {
		CALENDAR_LOCALE,
		CALENDAR_TRIGGER,
		DATE_BOX,
		DAY_RANGE,
		NATIVE_DATE,
		POPOVER,
		SEGMENT,
		WEEK_STARTS_ON,
		commitTyped,
		toDate
	} from './calendar';
	import { ICON } from './icon';

	type Range = { from: string; to: string };

	const ENDS = [
		{ type: 'start', label: 'From' },
		{ type: 'end', label: 'To' }
	] as const;

	let {
		label,
		from,
		to,
		min,
		max,
		onchange,
		class: className
	}: {
		/** Names the pair; its ends are "From" and "To". */
		label: string;
		/** `YYYY-MM-DD` days, as the URL and the API carry them. */
		from: string;
		to: string;
		min?: string;
		max?: string;
		/**
		 * Fires once a range is committed - both ends picked in the calendar, or
		 * typed and then Enter or leaving the field - and only whole, in order
		 * and within bounds, never with one end half done.
		 */
		onchange: (range: Range) => void;
		/** The box's size, fill and type step. */
		class?: string;
	} = $props();

	const id = $props.id();
	// The calendar hangs from the whole field, not from the glyph that opens it.
	let box = $state<HTMLElement | null>(null);

	let pending: Range | undefined;

	function emit(next: Range) {
		const { from: start, to: end } = next;
		if (!start || !end || start > end || (min && start < min) || (max && end > max)) return;
		if (start !== from || end !== to) onchange(next);
	}

	function commit() {
		if (pending) emit(pending);
		pending = undefined;
	}
</script>

{#if finePointer.current}
	<DateRangePicker.Root
		value={{ start: toDate(from), end: toDate(to) }}
		minValue={toDate(min)}
		maxValue={toDate(max)}
		locale={CALENDAR_LOCALE}
		weekStartsOn={WEEK_STARTS_ON}
		weekdayFormat="short"
		fixedWeeks
		onValueChange={(next) =>
			(pending = { from: next.start?.toString() ?? '', to: next.end?.toString() ?? '' })}
		onOpenChangeComplete={(open) => {
			if (!open) commit();
		}}
	>
		<DateRangePicker.Label class="sr-only">{label}</DateRangePicker.Label>
		<div
			bind:this={box}
			class={cn(DATE_BOX, className)}
			role="presentation"
			{...commitTyped(commit)}
		>
			{#each ENDS as end (end.type)}
				{#if end.type === 'end'}
					<span aria-hidden="true" class="text-muted-foreground">–</span>
				{/if}
				<!-- Each end's parts are only "day", "month", "year" to a screen reader,
				     so a group says which end they belong to. -->
				<div role="group" aria-label={end.label}>
					<DateRangePicker.Input type={end.type} class="flex items-center">
						{#snippet children({ segments })}
							{#each segments as segment, i (i)}
								<DateRangePicker.Segment part={segment.part} class={SEGMENT}>
									{segment.value}
								</DateRangePicker.Segment>
							{/each}
						{/snippet}
					</DateRangePicker.Input>
				</div>
			{/each}
			<DateRangePicker.Trigger class={CALENDAR_TRIGGER} aria-label="Open calendar">
				<CalendarIcon size={ICON.xs} aria-hidden="true" />
			</DateRangePicker.Trigger>
		</div>
		<Portal>
			<DateRangePicker.Content customAnchor={box} sideOffset={4} align="start" class={POPOVER}>
				<DateRangePicker.Calendar>
					{#snippet children({ months, weekdays })}
						<CalendarMonths parts={DateRangePicker} {months} {weekdays} dayClass={DAY_RANGE} />
					{/snippet}
				</DateRangePicker.Calendar>
			</DateRangePicker.Content>
		</Portal>
	</DateRangePicker.Root>
{:else}
	<div class={cn(DATE_BOX, className)} role="group" aria-label={label}>
		<label class="sr-only" for="{id}-from">{ENDS[0].label}</label>
		<input
			id="{id}-from"
			type="date"
			value={from}
			{min}
			max={to || max}
			class={NATIVE_DATE}
			onchange={(event) => emit({ from: event.currentTarget.value, to })}
		/>
		<span aria-hidden="true" class="text-muted-foreground">–</span>
		<label class="sr-only" for="{id}-to">{ENDS[1].label}</label>
		<input
			id="{id}-to"
			type="date"
			value={to}
			min={from || min}
			{max}
			class={NATIVE_DATE}
			onchange={(event) => emit({ from, to: event.currentTarget.value })}
		/>
	</div>
{/if}
