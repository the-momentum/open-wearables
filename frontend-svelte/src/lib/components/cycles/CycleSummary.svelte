<script lang="ts">
	import CalendarDays from '@lucide/svelte/icons/calendar-days';
	import Droplet from '@lucide/svelte/icons/droplet';
	import Heart from '@lucide/svelte/icons/heart';
	import EventTotals from '$lib/components/events/EventTotals.svelte';
	import type { CycleTotals } from '$lib/cycles/totals';
	import { DASH, formatDays } from '$lib/utils/format';

	let { userId }: { userId: string } = $props();

	const inDays = (value: number | null) => (value === null ? DASH : formatDays(value));
</script>

<EventTotals
	url={() => `/users/${userId}/womens-health/totals`}
	label="Cycle totals"
	noun="cycles"
	figures={(totals: CycleTotals) => [
		{ icon: Heart, label: 'Cycles', value: totals.count },
		{ icon: CalendarDays, label: 'Avg cycle', value: inDays(totals.averageLength) },
		{ icon: Droplet, label: 'Avg period', value: inDays(totals.averagePeriod) }
	]}
/>
