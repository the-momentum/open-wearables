<script lang="ts">
	import ChartRow from '$lib/components/ui/ChartRow.svelte';
	import { MICRO } from '$lib/components/ui/typography';

	let {
		rows,
		from,
		to,
		formatTime,
		label
	}: {
		/** One lane per key, drawn top to bottom in the order given. */
		rows: {
			key: string;
			label: string;
			shade: string;
			spans: { start: number; end: number; title: string }[];
		}[];
		from: number;
		to: number;
		formatTime: (at: number) => string;
		label: string;
	} = $props();

	const span = $derived(Math.max(to - from, 1));
	const at = (time: number) => ((time - from) / span) * 100;
</script>

<!-- Lanes rather than a stepped line: a stage is a block of time, and blocks the
     reader can point at carry their own numbers without a hover layer. Each lane
     is a `ChartRow`, so it lines up with a stage breakdown drawn beneath it. -->
<div class="flex flex-col gap-2" role="img" aria-label={label}>
	<div class="flex flex-col gap-1">
		{#each rows as row (row.key)}
			<ChartRow label={row.label}>
				<div class="relative h-5 overflow-hidden rounded bg-surface-muted/60">
					{#each row.spans as gap (`${gap.start}-${gap.end}`)}
						<span
							class="absolute inset-y-0 rounded-sm {row.shade}"
							style="left: {at(gap.start)}%; width: {Math.max(at(gap.end) - at(gap.start), 0.4)}%"
							title={gap.title}
						></span>
					{/each}
				</div>
			</ChartRow>
		{/each}
	</div>

	<ChartRow>
		<div class="flex justify-between tabular-nums {MICRO}">
			<span>{formatTime(from)}</span>
			<span>{formatTime(to)}</span>
		</div>
	</ChartRow>
</div>
