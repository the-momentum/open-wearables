<script lang="ts">
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import CircleCheck from '@lucide/svelte/icons/circle-check';
	import CircleX from '@lucide/svelte/icons/circle-x';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import ShareBar from '$lib/components/charts/ShareBar.svelte';
	import Figures from '$lib/components/ui/Figures.svelte';
	import { formatNumber, formatPercent } from '$lib/utils/format';
	import { humanise } from '$lib/utils/text';
	import type { overview } from '$lib/syncs/runs';

	let { counts }: { counts: ReturnType<typeof overview> } = $props();

	const figures = $derived([
		{ icon: LoaderCircle, label: 'Running now', value: formatNumber(counts.running) },
		{ icon: CircleX, label: 'Failed', value: formatNumber(counts.failed) },
		{ icon: CircleAlert, label: 'Need a look', value: formatNumber(counts.attention) },
		{ icon: CircleCheck, label: 'Completed', value: formatNumber(counts.completed) }
	]);

	const mix = $derived(counts.mix.map((part) => ({ ...part, label: humanise(part.key) })));
</script>

<div class="flex flex-col gap-4">
	<Figures {figures} label="Syncs in the window" />
	<!-- The whole mix, so the figures above can be read against it: most syncs
	     find nothing new, and that is what "skipped" means. -->
	<ShareBar
		parts={mix}
		format={(part, total) => `${formatNumber(part.value)} · ${formatPercent(part.value, total)}`}
	/>
</div>
