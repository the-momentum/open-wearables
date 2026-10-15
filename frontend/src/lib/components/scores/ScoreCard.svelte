<script lang="ts">
	import AccordionCard from '$lib/components/events/AccordionCard.svelte';
	import ProviderMark from '$lib/components/providers/ProviderMark.svelte';
	import { HEADING } from '$lib/components/ui/typography';
	import type { DayScores } from '$lib/scores/group';
	import { formatLocalDay } from '$lib/utils/format';
	import ScoreDetails from './ScoreDetails.svelte';
	import ScoreRow from './ScoreRow.svelte';

	let {
		day,
		labelFor,
		colourFor
	}: {
		day: DayScores;
		labelFor: (provider: string) => string;
		colourFor: (provider: string) => string;
	} = $props();
</script>

<!-- No icon: five measures on a card would all wear the same calendar, and the
     icons belong to the rows, where they tell them apart. -->
<AccordionCard>
	{#snippet title()}
		<span class={HEADING}>{formatLocalDay(day.recordedAt, day.zoneOffset)}</span>
	{/snippet}

	{#snippet aside()}
		<!-- Marks only, no device: a score names the provider that computed it and
		     never which watch fed it. Several of them is the point of the card. -->
		<span class="flex shrink-0 items-center gap-1">
			{#each day.providers as provider (provider)}
				<ProviderMark {provider} label={labelFor(provider)} size="sm" />
			{/each}
		</span>
	{/snippet}

	{#snippet metrics()}
		<div class="flex flex-col gap-2.5">
			{#each day.categories as scores (scores.category)}
				<ScoreRow {scores} {labelFor} />
			{/each}
		</div>
	{/snippet}

	{#snippet details()}
		<ScoreDetails {day} {labelFor} {colourFor} />
	{/snippet}
</AccordionCard>
