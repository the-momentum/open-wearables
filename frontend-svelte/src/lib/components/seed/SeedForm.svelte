<script lang="ts">
	import type { ProviderBrand } from '$lib/providers/labels';
	import { draftFrom, matchingPreset, problems, type Draft } from '$lib/seed/draft';
	import type { SeriesGroup } from '$lib/seed/catalogue';
	import { audienceSummary, perUser, windowSummary } from '$lib/seed/summary';
	import type { SeedPreset, SleepProfile } from '$lib/seed/types';
	import GenerateCard from './GenerateCard.svelte';
	import PresetPicker from './PresetPicker.svelte';
	import SeedBasics from './SeedBasics.svelte';
	import SeriesSection from './SeriesSection.svelte';
	import SleepSection from './SleepSection.svelte';
	import WorkoutSection from './WorkoutSection.svelte';

	let {
		presets,
		sleepProfiles,
		series,
		providers,
		message,
		queued
	}: {
		presets: SeedPreset[];
		sleepProfiles: SleepProfile[];
		series: SeriesGroup[];
		providers: ProviderBrand[];
		message?: string;
		queued?: { seed: number | null; users: number };
	} = $props();

	// The quickest to generate, which is what a first click in a test tool wants.
	// svelte-ignore state_referenced_locally
	const start = presets.find((preset) => preset.id === 'minimal') ?? presets[0];

	let draft = $state<Draft>(draftFrom(start.profile, { users: 1, seed: null }));

	/** A preset brings its data; how many users and which seed are yours. */
	const pick = (preset: SeedPreset) =>
		(draft = draftFrom(preset.profile, { users: draft.users, seed: draft.seed }));

	const active = $derived(matchingPreset(draft, presets));
	const found = $derived(problems(draft));

	const labelFor = (slug: string) =>
		providers.find((provider) => provider.provider === slug)?.name ?? slug;

	const summary = $derived({
		who: audienceSummary(draft, labelFor),
		what: perUser(draft),
		when: windowSummary(draft.window)
	});
</script>

<div class="flex flex-col gap-5">
	<PresetPicker {presets} {active} onpick={pick} />

	<SeedBasics bind:draft {providers} />

	<div class="flex flex-col gap-3">
		<WorkoutSection bind:workouts={draft.workouts} />
		<SleepSection bind:sleep={draft.sleep} profiles={sleepProfiles} />
		<SeriesSection bind:series={draft.series} groups={series} workouts={draft.workouts.on} />
	</div>

	<GenerateCard
		payload={JSON.stringify({ draft, preset: active })}
		{summary}
		problems={found}
		{message}
		{queued}
	/>
</div>
