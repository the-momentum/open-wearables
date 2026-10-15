<script lang="ts">
	import Scale from '@lucide/svelte/icons/scale';
	import { page } from '$app/state';
	import { bodyGroups, composition } from '$lib/body/metrics';
	import VitalTrends from '$lib/components/body/VitalTrends.svelte';
	import FilterBar from '$lib/components/filters/FilterBar.svelte';
	import ProviderMark from '$lib/components/providers/ProviderMark.svelte';
	import Caption from '$lib/components/ui/Caption.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import FieldGroups from '$lib/components/ui/FieldGroups.svelte';
	import Figures from '$lib/components/ui/Figures.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { providerLabel } from '$lib/providers/labels';
	import { withParams } from '$lib/utils/url';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const hrefFor = (changes: Record<string, string | null>) => withParams(page.url, changes);
	const label = $derived(data.body ? providerLabel(data.providers, data.body.source.provider) : '');

	// A function, so the period it reads is the one in force when the trends fetch.
	const trendUrl = () => {
		const window = data.window!;
		return `/users/${page.params.id}/body/samples?${new URLSearchParams({
			from: window.from.toISOString(),
			to: window.to.toISOString(),
			seconds: String(Math.round((window.to.getTime() - window.from.getTime()) / 1000))
		})}`;
	};
</script>

<div class="flex flex-col gap-6">
	<!-- Only the period: this endpoint takes no provider, and the one it read from
	     is named beside the figures instead. -->
	<FilterBar
		period={data.period}
		{hrefFor}
		providers={[]}
		labelFor={(entry) => entry}
		selected=""
		periodLabel="Trend period"
	/>

	{#if !data.body}
		<Card>
			<EmptyState
				icon={Scale}
				title="No body data recorded"
				description="Weight, composition and vitals all come from the time series, so a user whose providers send none has nothing here."
			/>
		</Card>
	{:else}
		<div class="flex flex-col gap-6 border-t border-border pt-6">
			<div class="flex flex-col gap-3">
				<Figures figures={composition(data.body)} label="Body composition" />
				<p class="flex items-center gap-1.5 {MICRO}">
					<ProviderMark provider={data.body.source.provider} {label} size="sm" />
					Latest reading from {label}{data.body.source.device_name
						? ` · ${data.body.source.device_name}`
						: ''}
				</p>
			</div>

			<div class="flex flex-col gap-2">
				<Caption>Vitals over the period</Caption>
				<VitalTrends
					url={trendUrl}
					from={data.window!.from.getTime()}
					to={data.window!.to.getTime()}
				/>
			</div>

			<FieldGroups groups={bodyGroups(data.body)} />
		</div>
	{/if}
</div>
