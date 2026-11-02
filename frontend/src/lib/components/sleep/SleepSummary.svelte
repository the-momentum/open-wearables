<script lang="ts">
	import BedDouble from '@lucide/svelte/icons/bed-double';
	import Gauge from '@lucide/svelte/icons/gauge';
	import Moon from '@lucide/svelte/icons/moon';
	import Sunrise from '@lucide/svelte/icons/sunrise';
	import EventTotals from '$lib/components/events/EventTotals.svelte';
	import type { SleepTotals } from '$lib/sleep/totals';
	import { DASH, formatDuration, formatNumber } from '$lib/utils/format';

	let { userId, search }: { userId: string; search: string } = $props();
</script>

<EventTotals
	url={() => `/users/${userId}/sleep/totals${search}`}
	label="Sleep totals"
	noun="sessions"
	figures={(totals: SleepTotals) => [
		{ icon: Moon, label: 'Sessions', value: totals.count },
		{ icon: BedDouble, label: 'Time asleep', value: formatDuration(totals.asleepSeconds) },
		{
			icon: Gauge,
			label: 'Avg efficiency',
			value: totals.efficiency === null ? DASH : formatNumber(totals.efficiency, '%')
		},
		{ icon: Sunrise, label: 'Naps', value: totals.naps }
	]}
/>
