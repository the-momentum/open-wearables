<script lang="ts">
	import TrendingUp from '@lucide/svelte/icons/trending-up';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import { TONE_COLOUR } from '$lib/components/ui/tone';
	import { FOOTNOTE, MICRO } from '$lib/components/ui/typography';
	import { GROWTH } from '$lib/lifecycle/growth';
	import {
		ARCHIVE_RATIO_LABEL,
		archivalEffective,
		dailyIngest,
		growthOf,
		liveBytes,
		project,
		PROJECTION_MONTHS
	} from '$lib/lifecycle/projection';
	import type { Policy, StorageEstimate } from '$lib/lifecycle/types';
	import { formatBytes } from '$lib/utils/format';
	import ProjectionChart from './ProjectionChart.svelte';

	let { storage, policy }: { storage: StorageEstimate; policy: Policy } = $props();

	// Drawn off the draft, not the saved settings: the chart is how you see what
	// a change would do before you commit to it.
	const growth = $derived(GROWTH[growthOf(policy)]);
	const colour = $derived(TONE_COLOUR[growth.tone]);
	const points = $derived(project(storage, policy));
	const today = $derived(points[0].bytes);
	const later = $derived(points[PROJECTION_MONTHS].bytes);
</script>

<Card icon={TrendingUp} title="Growth projection" description={growth.description}>
	{#snippet action()}
		<Badge tone={growth.tone} class="font-mono">{growth.label}</Badge>
	{/snippet}

	<div class="flex flex-col gap-4">
		<div class="flex flex-wrap items-baseline gap-x-6 gap-y-1">
			<div>
				<span class={MICRO}>Time-series storage today</span>
				<p class="text-lg font-semibold text-foreground tabular-nums">{formatBytes(today)}</p>
			</div>
			<div>
				<span class={MICRO}>In {PROJECTION_MONTHS} months</span>
				<p class="text-lg font-semibold tabular-nums" style="color: {colour}">
					{formatBytes(later)}
				</p>
			</div>
		</div>

		<ProjectionChart {points} {colour} />

		<div class="flex flex-col gap-1 {FOOTNOTE}">
			{#if storage.live_row_count > 0}
				<p>
					Daily ingest ≈ <strong class="font-medium text-muted-foreground"
						>{formatBytes(dailyIngest(storage))}/day</strong
					>
					— the live table ({formatBytes(liveBytes(storage))}) over the {Math.max(
						storage.live_data_span_days,
						1
					)} days its data covers.
					{#if archivalEffective(policy)}Archived rows are assumed to take ~{ARCHIVE_RATIO_LABEL} of the
						raw volume.{/if}
				</p>
			{:else}
				<p>No live data yet, so the line stays at today's size.</p>
			{/if}
			<p>
				Live and archive tables only; the rest of the database is left out, since no policy here
				changes it. An estimate — it moves with devices, sampling rates and schema changes.
			</p>
		</div>
	</div>
</Card>
