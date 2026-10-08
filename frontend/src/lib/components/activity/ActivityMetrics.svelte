<script lang="ts">
	import Flame from '@lucide/svelte/icons/flame';
	import Footprints from '@lucide/svelte/icons/footprints';
	import HeartPulse from '@lucide/svelte/icons/heart-pulse';
	import Route from '@lucide/svelte/icons/route';
	import type { ActivityDay } from '$lib/activity/types';
	import MetricRow from '$lib/components/events/MetricRow.svelte';
	import { formatDistance, formatNumber } from '$lib/utils/format';

	let { day }: { day: ActivityDay } = $props();

	// A fixed set, dashes and all: an empty slot says the provider sent nothing,
	// and cards that shed columns are cards you cannot scan down a column of.
	const metrics = $derived([
		{ icon: Footprints, label: 'Steps', value: formatNumber(day.steps) },
		{ icon: Route, label: 'Distance', value: formatDistance(day.distance_meters) },
		{
			icon: Flame,
			label: 'Active energy',
			value: formatNumber(day.active_calories_kcal, ' kcal')
		},
		{
			icon: HeartPulse,
			label: 'Avg HR',
			value: formatNumber(day.heart_rate?.avg_bpm ?? null, ' bpm')
		}
	]);
</script>

<MetricRow {metrics} />
