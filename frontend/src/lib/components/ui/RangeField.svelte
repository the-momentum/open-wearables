<script lang="ts">
	import { cn } from '$lib/utils/cn';
	import { FIELD } from './field';
	import { MICRO } from './typography';

	let {
		label,
		value = $bindable([0, 0]),
		min,
		max,
		step = 1,
		unit,
		class: className
	}: {
		label: string;
		/** Low and high, bound as one pair so the two can never be separated. */
		value?: [number, number];
		min?: number;
		max?: number;
		step?: number;
		unit?: string;
		class?: string;
	} = $props();

	const BOX = `${FIELD} w-20 px-2.5 text-center tabular-nums`;
</script>

<fieldset class={cn('flex flex-col gap-1.5', className)}>
	<legend class="{MICRO} mb-1.5">{label}</legend>
	<div class="flex items-center gap-2">
		<input
			type="number"
			inputmode="numeric"
			aria-label="{label}, from"
			{min}
			{max}
			{step}
			bind:value={value[0]}
			class={BOX}
		/>
		<span aria-hidden="true" class="text-muted-foreground">–</span>
		<input
			type="number"
			inputmode="numeric"
			aria-label="{label}, to"
			{min}
			{max}
			{step}
			bind:value={value[1]}
			class={BOX}
		/>
		{#if unit}<span class="text-sm text-muted-foreground">{unit}</span>{/if}
	</div>
</fieldset>
