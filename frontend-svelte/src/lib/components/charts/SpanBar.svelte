<script lang="ts">
	export type Span = { title: string; shade: string; from: number; to: number };

	let {
		spans,
		to,
		marker = null
	}: {
		/** Inclusive whole units — a span from 1 to 5 covers five of them. */
		spans: Span[];
		/** The scale, shared by every bar on a page so their widths compare. */
		to: number;
		/** A point worth calling out, where there is one. */
		marker?: { at: number; title: string } | null;
	} = $props();

	const at = (unit: number) => ((unit - 1) / to) * 100;
</script>

<!-- One track of coloured spans. What the colours mean is the caller's to say:
     a legend above the list beats the same key repeated on every row. -->
<div class="relative h-6 min-w-0 flex-1 overflow-hidden rounded bg-surface-muted/60">
	{#each spans as span (span.from)}
		<span
			class="absolute inset-y-0 {span.shade}"
			style="left: {at(span.from)}%; width: {at(span.to + 1) - at(span.from)}%"
			title={span.title}
		></span>
	{/each}

	{#if marker}
		<span
			aria-hidden="true"
			class="absolute inset-y-0 w-0.5 bg-foreground"
			style="left: {at(marker.at)}%"
			title={marker.title}
		></span>
	{/if}
</div>
