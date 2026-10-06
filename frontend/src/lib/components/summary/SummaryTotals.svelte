<script lang="ts">
	import Database from '@lucide/svelte/icons/database';
	import Dumbbell from '@lucide/svelte/icons/dumbbell';
	import Moon from '@lucide/svelte/icons/moon';
	import Figures from '$lib/components/ui/Figures.svelte';
	import type { Totals } from '$lib/summary/narrow';

	let { summary }: { summary: Totals } = $props();

	const figures = $derived([
		{ icon: Database, label: 'Data points', value: summary.total_data_points },
		{ icon: Dumbbell, label: 'Workouts', value: summary.total_workouts },
		{ icon: Moon, label: 'Sleep events', value: summary.total_sleep_events }
	]);
</script>

<Figures {figures} label="Stored data totals" />
