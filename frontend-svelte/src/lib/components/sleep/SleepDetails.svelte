<script lang="ts">
	import Layers from '@lucide/svelte/icons/layers';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import DistributionBar from '$lib/components/charts/DistributionBar.svelte';
	import IntervalChart from '$lib/components/charts/IntervalChart.svelte';
	import Caption from '$lib/components/ui/Caption.svelte';
	import FieldGroups from '$lib/components/ui/FieldGroups.svelte';
	import { NOTE } from '$lib/components/ui/typography';
	import { detailGroups } from '$lib/sleep/fields';
	import { stageLabel, stageLanes, stageRows } from '$lib/sleep/stages';
	import type { SleepSession } from '$lib/sleep/types';
	import { formatDuration, formatLocalTime } from '$lib/utils/format';

	let { session, ondelete }: { session: SleepSession; ondelete: () => void } = $props();

	const clock = (iso: string) => formatLocalTime(iso, session.zone_offset);

	const lanes = $derived(
		stageLanes(
			session.sleep_stage_intervals ?? [],
			(span, seconds) =>
				`${stageLabel(span.stage)} · ${clock(span.start_time)}–${clock(span.end_time)} · ${formatDuration(seconds)}`
		)
	);

	const rows = $derived(stageRows(session));
</script>

<div class="flex flex-col gap-5 border-t border-border pt-4">
	<div class="flex flex-col gap-1.5">
		<Caption icon={Layers}>Through the {session.is_nap ? 'nap' : 'night'}</Caption>

		{#if lanes.length > 0}
			<IntervalChart
				rows={lanes}
				from={new Date(session.start_time).getTime()}
				to={new Date(session.end_time).getTime()}
				formatTime={(at) => clock(new Date(at).toISOString())}
				label="Sleep stages across the session"
			/>
		{:else}
			<!-- Most providers send per-stage minutes but no intervals, so the strip
			     below still has something to say. -->
			<p class={NOTE}>
				{rows.length > 0
					? 'This provider reports how long each stage lasted, but not when.'
					: 'No stage breakdown was stored for this session.'}
			</p>
		{/if}
	</div>

	<DistributionBar title="Time in each stage" icon={Layers} {rows} />

	<FieldGroups groups={detailGroups(session)} />

	<div class="flex justify-end border-t border-border pt-3">
		<button
			type="button"
			onclick={ondelete}
			class="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-danger"
		>
			<Trash2 size={14} aria-hidden="true" />
			Delete session
		</button>
	</div>
</div>
