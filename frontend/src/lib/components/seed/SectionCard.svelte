<script lang="ts">
	import type { Component, Snippet } from 'svelte';
	import AccordionCard from '$lib/components/events/AccordionCard.svelte';
	import Switch from '$lib/components/ui/Switch.svelte';
	import { HEADING, MICRO } from '$lib/components/ui/typography';

	// `title` is also the name of the snippet the card takes, which would shadow it.
	let {
		icon,
		title: name,
		summary,
		on = $bindable(true),
		children
	}: {
		icon: Component;
		title: string;
		/** What the section holds, in one line, for while it is folded. */
		summary: string;
		on?: boolean;
		children: Snippet;
	} = $props();
</script>

<!-- One kind of data to generate: folded to its summary, a switch beside it. -->
<AccordionCard {icon}>
	{#snippet title()}<span class={HEADING}>{name}</span>{/snippet}
	{#snippet when()}<span class={MICRO}>{summary}</span>{/snippet}
	{#snippet control()}<Switch bind:checked={on} label="Generate {name.toLowerCase()}" />{/snippet}

	{#snippet details()}
		<div class="flex flex-col gap-4 border-t border-border pt-4" class:opacity-50={!on}>
			{@render children()}
		</div>
	{/snippet}
</AccordionCard>
