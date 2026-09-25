<script lang="ts">
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
     reader can point at carry their own numbers without a hover layer. -->
<div class="flex flex-col gap-2" role="img" aria-label={label}>
	<div class="flex flex-col gap-1">
		{#each rows as row (row.key)}
			<div class="flex items-center gap-3">
				<span class="w-16 shrink-0 truncate text-xs text-foreground/80 sm:w-20">{row.label}</span>
				<div class="relative h-5 min-w-0 flex-1 overflow-hidden rounded bg-surface-muted/60">
					{#each row.spans as gap (gap.start)}
						<span
							class="absolute inset-y-0 rounded-sm {row.shade}"
							style="left: {at(gap.start)}%; width: {Math.max(at(gap.end) - at(gap.start), 0.4)}%"
							title={gap.title}
						></span>
					{/each}
				</div>
			</div>
		{/each}
	</div>

	<div class="flex justify-between pl-[4.75rem] tabular-nums {MICRO}">
		<span>{formatTime(from)}</span>
		<span>{formatTime(to)}</span>
	</div>
</div>
