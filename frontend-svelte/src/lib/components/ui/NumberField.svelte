<script lang="ts">
	import { cn } from '$lib/utils/cn';
	import { FIELD } from './field';
	import { MICRO } from './typography';

	let {
		label,
		value = $bindable(0),
		min,
		max,
		step = 1,
		unit,
		placeholder,
		hint,
		class: className
	}: {
		label: string;
		/** Null while the box is empty — which is what an optional number wants. */
		value?: number | null;
		min?: number;
		max?: number;
		step?: number;
		/** Said after the box, so the number reads as a quantity: "80 workouts". */
		unit?: string;
		placeholder?: string;
		hint?: string;
		class?: string;
	} = $props();

	const fieldId = $props.id();
	const hintId = `${fieldId}-hint`;
</script>

<div class={cn('flex flex-col gap-1.5', className)}>
	<label for={fieldId} class={MICRO}>{label}</label>
	<div class="flex items-center gap-2">
		<input
			id={fieldId}
			type="number"
			inputmode="numeric"
			{min}
			{max}
			{step}
			{placeholder}
			aria-describedby={hint ? hintId : undefined}
			bind:value
			class="{FIELD} w-24 px-3 tabular-nums"
		/>
		{#if unit}<span class="text-sm whitespace-nowrap text-muted-foreground">{unit}</span>{/if}
	</div>
	{#if hint}<span id={hintId} class={MICRO}>{hint}</span>{/if}
</div>
