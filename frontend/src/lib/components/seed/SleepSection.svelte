<script lang="ts">
	import Moon from '@lucide/svelte/icons/moon';
	import SwitchField from '$lib/components/ui/SwitchField.svelte';
	import SectionCard from './SectionCard.svelte';
	import NumberField from '$lib/components/ui/NumberField.svelte';
	import RangeField from '$lib/components/ui/RangeField.svelte';
	import { tagClass } from '$lib/components/ui/chip';
	import { MICRO } from '$lib/components/ui/typography';
	import { LIMITS, stagesOf, type Draft } from '$lib/seed/draft';
	import { sleepSummary } from '$lib/seed/summary';
	import type { SleepProfile } from '$lib/seed/types';
	import StagePreview from './StagePreview.svelte';

	let { sleep = $bindable(), profiles }: { sleep: Draft['sleep']; profiles: SleepProfile[] } =
		$props();

	const named = $derived(profiles.find((profile) => profile.id === sleep.stageProfile));
	const shown = $derived(stagesOf(sleep, profiles));
</script>

<SectionCard icon={Moon} title="Sleep" summary={sleepSummary(sleep, profiles)} bind:on={sleep.on}>
	<div class="flex flex-wrap items-end gap-x-6 gap-y-4">
		<NumberField
			label="Per user"
			bind:value={sleep.count}
			min={LIMITS.nights[0]}
			max={LIMITS.nights[1]}
			unit="nights"
		/>
		<RangeField
			label="Length"
			bind:value={sleep.duration}
			min={LIMITS.sleepMinutes[0]}
			max={LIMITS.sleepMinutes[1]}
			step={15}
			unit="min"
		/>
		<NumberField
			label="Nap chance"
			bind:value={sleep.napChance}
			min={LIMITS.percent[0]}
			max={LIMITS.percent[1]}
			unit="%"
		/>
		<SwitchField label="Short weekdays, long weekends" bind:checked={sleep.weekendCatchup} />
	</div>

	<div class="flex flex-col gap-2">
		<span class={MICRO}>Stages</span>
		<div class="flex flex-wrap gap-1.5">
			{#each profiles as profile (profile.id)}
				<button
					type="button"
					aria-pressed={sleep.stageProfile === profile.id}
					title={profile.description}
					onclick={() => (sleep.stageProfile = profile.id)}
					class={tagClass(sleep.stageProfile === profile.id)}
				>
					{profile.label}
				</button>
			{/each}
			<button
				type="button"
				aria-pressed={sleep.stageProfile === null}
				onclick={() => (sleep.stageProfile = null)}
				class={tagClass(sleep.stageProfile === null)}
			>
				Custom
			</button>
		</div>

		<StagePreview {...shown} />

		{#if named}
			<p class={MICRO}>{named.description}.</p>
		{:else}
			<div class="flex flex-wrap gap-x-6 gap-y-4 pt-1">
				<RangeField label="Deep" bind:value={sleep.deep} min={0} max={100} unit="%" />
				<RangeField label="REM" bind:value={sleep.rem} min={0} max={100} unit="%" />
				<RangeField label="Awake" bind:value={sleep.awake} min={0} max={100} unit="%" />
			</div>
		{/if}
	</div>
</SectionCard>
