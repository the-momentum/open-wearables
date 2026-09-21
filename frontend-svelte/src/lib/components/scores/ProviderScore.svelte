<script lang="ts">
	import ProviderMark from '$lib/components/providers/ProviderMark.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import type { ProviderReading } from '$lib/scores/group';
	import { showDecimal } from '$lib/utils/format';

	let { reading, labelFor }: { reading: ProviderReading; labelFor: (provider: string) => string } =
		$props();

	const label = $derived(labelFor(reading.provider));

	/** A mean stands in for the whole day, so the span it hides goes beside it. */
	const spread = $derived(
		reading.spread
			? `${Math.round(reading.spread.low)}–${Math.round(reading.spread.high)} over ${reading.readings} readings`
			: null
	);
</script>

<!-- The mark carries the provider, since a row holds two or three of these and
     the name would crowd out the number they are here for. -->
<div class="flex min-w-0 items-center gap-2" title={label}>
	<ProviderMark provider={reading.provider} {label} size="sm" />
	<dt class="sr-only">{label}</dt>
	<dd class="text-base font-semibold text-foreground tabular-nums">
		{showDecimal(reading.score)}
	</dd>

	{#if reading.qualifier}
		<dd><Badge>{reading.qualifier}</Badge></dd>
	{/if}
	{#if spread}
		<dd class="{MICRO} truncate tabular-nums">{spread}</dd>
	{/if}
</div>
