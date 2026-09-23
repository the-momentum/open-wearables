<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLInputAttributes } from 'svelte/elements';
	import { cn } from '$lib/utils/cn';
	import { FIELD } from './field';
	import { MICRO } from './typography';

	let {
		label,
		hint,
		value = $bindable(''),
		class: className,
		trailing,
		...rest
	}: HTMLInputAttributes & {
		label: string;
		/** Described, not named: inside the label it becomes part of the field's name. */
		hint?: string;
		value?: string;
		/** A control sitting inside the box — the password eye, so far. */
		trailing?: Snippet;
	} = $props();

	const fieldId = $props.id();
	const hintId = `${fieldId}-hint`;
</script>

<div class="flex flex-col gap-1.5">
	<label for={fieldId} class="text-sm font-medium">{label}</label>
	<div class="relative">
		<input
			id={fieldId}
			bind:value
			aria-describedby={hint ? hintId : undefined}
			{...rest}
			class={cn(FIELD, 'px-3', className)}
		/>
		{@render trailing?.()}
	</div>
	{#if hint}<span id={hintId} class={MICRO}>{hint}</span>{/if}
</div>
