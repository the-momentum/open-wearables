<script lang="ts">
	import Dumbbell from '@lucide/svelte/icons/dumbbell';
	import SectionCard from './SectionCard.svelte';
	import NumberField from '$lib/components/ui/NumberField.svelte';
	import RangeField from '$lib/components/ui/RangeField.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { WORKOUT_TYPE_GROUPS } from '$lib/seed/catalogue';
	import { LIMITS, type Draft } from '$lib/seed/draft';
	import { workoutSummary } from '$lib/seed/summary';
	import { humanise } from '$lib/utils/text';
	import GroupedChips from './GroupedChips.svelte';

	let { workouts = $bindable() }: { workouts: Draft['workouts'] } = $props();

	const groups = WORKOUT_TYPE_GROUPS.map((group) => ({
		label: group.label,
		items: group.types.map((type) => ({ id: type, label: humanise(type) }))
	}));

	// Null means every type, which is a different request from a list of all
	// the ones shown here: the shown list leaves the niche ones out.
	const scope = $derived(workouts.types === null ? 'any' : 'some');
	const pickScope = (value: string) => (workouts.types = value === 'any' ? null : []);
</script>

<SectionCard
	icon={Dumbbell}
	title="Workouts"
	summary={workoutSummary(workouts)}
	bind:on={workouts.on}
>
	<div class="flex flex-wrap gap-x-6 gap-y-4">
		<NumberField
			label="Per user"
			bind:value={workouts.count}
			min={LIMITS.workouts[0]}
			max={LIMITS.workouts[1]}
			unit="workouts"
		/>
		<RangeField
			label="Length"
			bind:value={workouts.duration}
			min={LIMITS.workoutMinutes[0]}
			max={LIMITS.workoutMinutes[1]}
			unit="min"
		/>
	</div>
	<div class="flex flex-wrap gap-x-6 gap-y-4">
		<RangeField label="Lowest heart rate" bind:value={workouts.hrMin} unit="bpm" />
		<RangeField label="Highest heart rate" bind:value={workouts.hrMax} unit="bpm" />
		<RangeField label="Steps" bind:value={workouts.steps} step={100} />
	</div>

	<div class="flex flex-col gap-3">
		<div class="flex flex-col gap-1.5">
			<span class={MICRO}>Types</span>
			<Segmented
				label="Workout types"
				items={[
					{ value: 'any', label: 'Any type' },
					{ value: 'some', label: 'Only these' }
				]}
				selected={scope}
				onselect={pickScope}
			/>
		</div>
		{#if workouts.types !== null}
			<GroupedChips {groups} bind:chosen={workouts.types} />
		{/if}
	</div>
</SectionCard>
