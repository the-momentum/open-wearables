<script lang="ts">
	import Activity from '@lucide/svelte/icons/activity';
	import SwitchField from '$lib/components/ui/SwitchField.svelte';
	import SectionCard from './SectionCard.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import type { SeriesGroup } from '$lib/seed/catalogue';
	import type { Draft } from '$lib/seed/draft';
	import { seriesSummary } from '$lib/seed/summary';
	import { humanise } from '$lib/utils/text';
	import GroupedChips from './GroupedChips.svelte';

	let {
		series = $bindable(),
		groups,
		workouts
	}: {
		series: Draft['series'];
		groups: SeriesGroup[];
		/** The workout-bound ones only appear inside workouts. */
		workouts: boolean;
	} = $props();

	const chipGroups = $derived(
		groups.map((group) => ({
			label: group.label,
			items: group.types.map((type) => ({ id: type, label: humanise(type) }))
		}))
	);
</script>

<SectionCard
	icon={Activity}
	title="Time series"
	summary={seriesSummary(series)}
	bind:on={series.on}
>
	<GroupedChips groups={chipGroups} bind:chosen={series.types} />

	{#if !workouts}
		<p class={MICRO}>
			With workouts off, the "During workouts" types have nothing to be recorded in.
		</p>
	{/if}

	<SwitchField
		label="Blood pressure, as systolic and diastolic pairs"
		bind:checked={series.bloodPressure}
	/>
</SectionCard>
