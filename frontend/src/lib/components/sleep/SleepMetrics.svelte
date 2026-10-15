<script lang="ts">
	import BedDouble from '@lucide/svelte/icons/bed-double';
	import Gauge from '@lucide/svelte/icons/gauge';
	import Layers from '@lucide/svelte/icons/layers';
	import Moon from '@lucide/svelte/icons/moon';
	import MetricCell from '$lib/components/events/MetricCell.svelte';
	import MetricRow from '$lib/components/events/MetricRow.svelte';
	import { stageRows } from '$lib/sleep/stages';
	import type { SleepSession } from '$lib/sleep/types';
	import { DASH, formatDuration, formatNumber } from '$lib/utils/format';

	let { session }: { session: SleepSession } = $props();

	const metrics = $derived([
		{ icon: Moon, label: 'Asleep', value: formatDuration(session.sleep_duration_seconds) },
		{
			icon: BedDouble,
			label: 'In bed',
			value: formatDuration(session.time_in_bed_seconds ?? session.duration_seconds)
		},
		{ icon: Gauge, label: 'Efficiency', value: formatNumber(session.efficiency_percent, '%') }
	]);

	// The fourth slot was one named stage, which ranked it above the others for no
	// reason. A strip shows the whole mix and privileges none of them.
	const stages = $derived(stageRows(session));
	const total = $derived(stages.reduce((sum, row) => sum + row.seconds, 0));
</script>

<MetricRow {metrics}>
	<MetricCell icon={Layers} label="Stages">
		{#if total > 0}
			<span class="flex h-2.5 w-full overflow-hidden rounded-full bg-surface-muted">
				{#each stages as row (row.label)}
					<span
						class={row.shade}
						style="width: {(row.seconds / total) * 100}%"
						title="{row.label} · {formatDuration(row.seconds)}"
					></span>
				{/each}
			</span>
		{:else}
			<span class="text-sm font-medium text-foreground">{DASH}</span>
		{/if}
	</MetricCell>
</MetricRow>
