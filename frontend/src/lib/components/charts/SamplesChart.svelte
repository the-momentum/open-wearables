<script lang="ts">
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
	import { MICRO, NOTE } from '$lib/components/ui/typography';
	import { toSeries, type Sample } from '$lib/timeseries/samples';
	import { resource } from '$lib/utils/resource.svelte';
	import LineChart from './LineChart.svelte';

	let {
		url,
		order,
		zones = null,
		from,
		to,
		formatTime,
		label,
		empty
	}: {
		/** A function, so the caller's reactive reads happen inside the fetch. */
		url: () => string;
		/** Which series to keep, in the order the chart stacks them. */
		order: string[];
		zones?: { type: string; label: string; zones: { max: number | null }[] } | null;
		from: number;
		to: number;
		formatTime: (at: number) => string;
		label: string;
		/** What to say when the window holds no readings at all. */
		empty: string;
	} = $props();

	// The caller only mounts this when a card opens, so the fetch is the
	// expansion: ten cards' worth of curves would be ten timeseries scans for the
	// nine nobody looks at.
	const fetched = resource<{ samples: Sample[]; truncated: boolean; resolution: string }>(() =>
		url()
	);

	const series = $derived(toSeries(fetched.current?.samples ?? [], order));
	const bucket = $derived(
		fetched.current && fetched.current.resolution !== 'raw' ? fetched.current : null
	);
</script>

{#if !fetched.settled}
	<Skeleton class="h-44" />
{:else if series.length === 0}
	<p class={NOTE}>{empty}</p>
{:else}
	<LineChart {series} {zones} {from} {to} {formatTime} {label} />

	{#if bucket}
		<!-- Say which, because an average is a different curve: the peaks a phone
		     shows are exactly what a bucket flattens. -->
		<p class={MICRO}>
			Too many readings to plot one by one, so these are averages per {bucket.resolution.replace(
				'min',
				' minute'
			)}{bucket.truncated ? ', and still more than one page holds' : ''}.
		</p>
	{/if}
{/if}
