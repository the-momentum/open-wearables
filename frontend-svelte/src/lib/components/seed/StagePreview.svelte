<script lang="ts">
	import ShareBar from '$lib/components/charts/ShareBar.svelte';
	import { stageShade } from '$lib/sleep/stages';
	import type { Range } from '$lib/seed/types';
	import { formatPercent } from '$lib/utils/format';

	let { deep, rem, awake }: { deep: Range; rem: Range; awake: Range } = $props();

	// A typical night from the ranges: each stage at its midpoint, light sleep
	// whatever is left — which is how the generator fills the rest too.
	const mid = ([low, high]: Range) => (low + high) / 2;
	const parts = $derived.by(() => {
		const shares = { deep: mid(deep), rem: mid(rem), awake: mid(awake) };
		const light = Math.max(100 - shares.deep - shares.rem - shares.awake, 0);
		return [
			{ key: 'deep', label: 'Deep', value: shares.deep, shade: stageShade('deep') },
			{ key: 'light', label: 'Light', value: light, shade: stageShade('light') },
			{ key: 'rem', label: 'REM', value: shares.rem, shade: stageShade('rem') },
			{ key: 'awake', label: 'Awake', value: shares.awake, shade: stageShade('awake') }
		];
	});
</script>

<ShareBar {parts} format={(part, total) => formatPercent(part.value, total)} />
