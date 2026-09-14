<script lang="ts">
	import Database from '@lucide/svelte/icons/database';
	import Dumbbell from '@lucide/svelte/icons/dumbbell';
	import Moon from '@lucide/svelte/icons/moon';
	import { CAPTION } from '$lib/components/ui/typography';
	import type { DataSummary } from '$lib/summary/types';

	let { summary }: { summary: DataSummary } = $props();

	const totals = $derived([
		{ icon: Database, label: 'Data points', value: summary.total_data_points },
		{ icon: Dumbbell, label: 'Workouts', value: summary.total_workouts },
		{ icon: Moon, label: 'Sleep events', value: summary.total_sleep_events }
	]);
</script>

<dl class="grid grid-cols-3 divide-x divide-border">
	{#each totals as total (total.label)}
		<div class="flex flex-col gap-1 px-3 first:pl-0 last:pr-0">
			<dt class="flex items-center gap-1.5">
				<total.icon size={12} aria-hidden="true" class="shrink-0 text-muted-foreground/50" />
				<span class="truncate {CAPTION}">{total.label}</span>
			</dt>
			<dd class="text-xl font-semibold text-foreground tabular-nums sm:text-2xl">{total.value}</dd>
		</div>
	{/each}
</dl>
