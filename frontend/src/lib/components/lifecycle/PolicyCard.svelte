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
		on,
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
		/** The sentence the number completes: "Delete samples older than". A stage without one is a plain switch. */
		lead?: string;
		/** What having it on means, for a stage without a number. */
		on?: string;
		/** What leaving it off means, which is not the same for both stages. */
		off: string;
		max?: number;
		enabled?: boolean;
		/** A number input binds a number, or null while it is empty. */
		days?: number | null;
	} = $props();

	const fieldId = $props.id();
	const noteId = `${fieldId}-note`;
</script>

<Card {icon} {title} {description}>
	{#snippet action()}
		<Switch bind:checked={enabled} label={toggle} />
	{/snippet}

	{#if lead}
		<!-- The number stays editable while the stage is off, so it can be set before the switch. -->
		<div class="flex flex-col gap-2">
			<div class="flex flex-wrap items-center gap-2 text-sm text-secondary-foreground">
				<label for={fieldId}>{lead}</label>
				<input
					id={fieldId}
					type="number"
					inputmode="numeric"
					min="1"
					{max}
					step="1"
					bind:value={days}
					aria-describedby={enabled ? undefined : noteId}
					class="{FIELD} w-24 px-3 tabular-nums"
				/>
				<span>days</span>
			</div>
			{#if !enabled}
				<p id={noteId} class="text-sm text-muted-foreground">{off}</p>
			{/if}
		</div>
	{:else}
		<p class="text-sm text-muted-foreground">{enabled ? on : off}</p>
	{/if}
</Card>
