<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import { cn } from '$lib/utils/cn';
	import { SELECT } from './field';
	import { ICON } from './icon';
	import { MICRO } from './typography';

	let {
		label,
		value,
		options,
		onselect,
		labelled = true,
		size = 'md',
		fill = false
	}: {
		label: string;
		value: string | number;
		options: { value: string | number; label: string }[];
		/** What to do with the new value - navigate, or change state in place. */
		onselect: (value: string) => void;
		/** False when something outside already captions it, as `FilterGroup` does. */
		labelled?: boolean;
		/** `sm` beside a pager, where the page-size picker sits. */
		size?: keyof typeof SELECT;
		/** Fills its row on a phone, where filters stack one per line. */
		fill?: boolean;
	} = $props();

	const id = $props.id();
</script>

<div
	class={cn('relative items-center', fill ? 'flex w-full sm:inline-flex sm:w-auto' : 'inline-flex')}
>
	<label class={labelled ? `sr-only sm:not-sr-only sm:mr-1.5 ${MICRO}` : 'sr-only'} for={id}>
		{label}
	</label>
	<select
		{id}
		{value}
		onchange={(event) => onselect(event.currentTarget.value)}
		class={cn(SELECT[size], fill && 'w-full sm:w-auto')}
	>
		{#each options as option (option.value)}
			<option value={option.value}>{option.label}</option>
		{/each}
	</select>
	<ChevronDown
		size={ICON.xs}
		aria-hidden="true"
		class="pointer-events-none absolute right-2 text-muted-foreground"
	/>
</div>
