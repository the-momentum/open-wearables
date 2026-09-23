<script lang="ts">
	import type { Component } from 'svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import Switch from '$lib/components/ui/Switch.svelte';
	import { FIELD } from '$lib/components/ui/field';

	let {
		icon,
		title,
		description,
		toggle,
		lead,
		off,
		max,
		enabled = $bindable(false),
		days = $bindable(null)
	}: {
		icon: Component;
		title: string;
		description: string;
		/** The switch's name for assistive tech. */
		toggle: string;
		/** The sentence the number completes: "Archive data older than". */
		lead: string;
		/** What leaving it off means, which is not the same for both stages. */
		off: string;
		max: number;
		enabled?: boolean;
		/** A number input binds a number, or null while it is empty. */
		days?: number | null;
	} = $props();

	const fieldId = $props.id();
</script>

<Card {icon} {title} {description}>
	{#snippet action()}
		<Switch bind:checked={enabled} label={toggle} />
	{/snippet}

	{#if enabled}
		<div class="flex flex-wrap items-center gap-2 text-sm text-foreground/90">
			<label for={fieldId}>{lead}</label>
			<input
				id={fieldId}
				type="number"
				inputmode="numeric"
				min="1"
				{max}
				step="1"
				bind:value={days}
				class="{FIELD} w-24 px-3 tabular-nums"
			/>
			<span>days</span>
		</div>
	{:else}
		<p class="text-sm text-muted-foreground">{off}</p>
	{/if}
</Card>
