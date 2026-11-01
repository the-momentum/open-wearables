<script lang="ts">
	import { NOTE } from '$lib/components/ui/typography';
	import { detailSections, hasDetail } from '$lib/scores/details';
	import type { DayScores } from '$lib/scores/group';
	import ScoreSection from './ScoreSection.svelte';

	let {
		day,
		labelFor,
		colourFor
	}: {
		day: DayScores;
		labelFor: (provider: string) => string;
		/** The page's palette, so a provider is one colour in a tile and in here. */
		colourFor: (provider: string) => string;
	} = $props();

	const sections = $derived(detailSections(day.categories, labelFor).filter(hasDetail));
</script>

<div class="flex flex-col gap-5 border-t border-border pt-4">
	{#each sections as section (section.category)}
		<ScoreSection {section} zoneOffset={day.zoneOffset} {colourFor} />
	{/each}

	{#if sections.length === 0}
		<p class={NOTE}>These providers sent scores and nothing they were made of.</p>
	{/if}
</div>
