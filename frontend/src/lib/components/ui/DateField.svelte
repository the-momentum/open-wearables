<script lang="ts">
	import CalendarIcon from '@lucide/svelte/icons/calendar';
	import { DatePicker } from 'bits-ui';
	import { cn } from '$lib/utils/cn';
	import { finePointer } from '$lib/utils/pointer';
	import CalendarMonths from './CalendarMonths.svelte';
	import {
		CALENDAR_LOCALE,
		CALENDAR_TRIGGER,
		DATE_BOX,
		DAY_SINGLE,
		NATIVE_DATE,
		POPOVER,
		SEGMENT,
		WEEK_STARTS_ON,
		commitTyped,
		toDate
	} from './calendar';
	import { ICON } from './icon';

	let {
		label,
		value,
		min,
		max,
		onchange,
		class: className
	}: {
		label: string;
		/** `YYYY-MM-DD`, as the URL and the API carry a day. */
		value: string;
		min?: string;
		max?: string;
		/**
		 * Fires once a day is committed - picked in the calendar, or typed and
		 * then Enter or leaving the field - and only a whole one within bounds,
		 * so a year typed digit by digit never passes through 0002.
		 */
		onchange: (value: string) => void;
		/** The box's size, fill and type step. */
		class?: string;
	} = $props();

	const id = $props.id();
	// The calendar hangs from the whole field, not from the glyph that opens it.
	let box = $state<HTMLElement | null>(null);
	let pending: string | undefined;

	function commit() {
		const next = pending;
		pending = undefined;
		if (!next || next === value || (min && next < min) || (max && next > max)) return;
		onchange(next);
	}
</script>

{#if finePointer.current}
	<DatePicker.Root
		value={toDate(value)}
		minValue={toDate(min)}
		maxValue={toDate(max)}
		locale={CALENDAR_LOCALE}
		weekStartsOn={WEEK_STARTS_ON}
		weekdayFormat="short"
		fixedWeeks
		onValueChange={(next) => (pending = next?.toString())}
		onOpenChangeComplete={(open) => {
			if (!open) commit();
		}}
	>
		<DatePicker.Label class="sr-only">{label}</DatePicker.Label>
		<DatePicker.Input
			bind:ref={box}
			class={cn(DATE_BOX, 'gap-0', className)}
			{...commitTyped(commit)}
		>
			{#snippet children({ segments })}
				{#each segments as segment, i (i)}
					<DatePicker.Segment part={segment.part} class={SEGMENT}>
						{segment.value}
					</DatePicker.Segment>
				{/each}
				<DatePicker.Trigger class={cn(CALENDAR_TRIGGER, 'ml-2')} aria-label="Open calendar">
					<CalendarIcon size={ICON.xs} aria-hidden="true" />
				</DatePicker.Trigger>
			{/snippet}
		</DatePicker.Input>
		<DatePicker.Portal>
			<DatePicker.Content customAnchor={box} sideOffset={4} align="start" class={POPOVER}>
				<DatePicker.Calendar>
					{#snippet children({ months, weekdays })}
						<CalendarMonths parts={DatePicker} {months} {weekdays} dayClass={DAY_SINGLE} />
					{/snippet}
				</DatePicker.Calendar>
			</DatePicker.Content>
		</DatePicker.Portal>
	</DatePicker.Root>
{:else}
	<div class={cn(DATE_BOX, className)}>
		<label class="sr-only" for={id}>{label}</label>
		<input
			{id}
			type="date"
			{value}
			{min}
			{max}
			class={NATIVE_DATE}
			onchange={(event) => {
				if (event.currentTarget.value) onchange(event.currentTarget.value);
			}}
		/>
	</div>
{/if}
