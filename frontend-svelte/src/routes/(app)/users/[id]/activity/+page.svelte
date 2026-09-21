<script lang="ts">
	import Activity from '@lucide/svelte/icons/activity';
	import { page } from '$app/state';
	import ActivityCard from '$lib/components/activity/ActivityCard.svelte';
	import ActivitySummary from '$lib/components/activity/ActivitySummary.svelte';
	import FilterBar from '$lib/components/filters/FilterBar.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import CursorBar from '$lib/components/events/CursorBar.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { cursorHrefs } from '$lib/lists/cursor';
	import { providerLabel } from '$lib/providers/labels';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const nav = $derived(cursorHrefs(page.url));
	const { hrefFor } = $derived(nav);

	const label = (entry: string) => providerLabel(data.providers, entry);
	const days = $derived(data.days.data);
</script>

<div class="flex flex-col gap-6">
	<!-- No provider control: the endpoint has no such parameter, because it picks
	     the winning source per day itself. Each card names the one it used. -->
	<FilterBar period={data.period} {hrefFor} providers={[]} labelFor={label} selected="" />

	<div class="flex flex-col gap-5 border-t border-border pt-6">
		<ActivitySummary userId={page.params.id ?? ''} search={page.url.search} />

		{#if days.length === 0}
			<Card>
				<EmptyState
					icon={Activity}
					title={data.period.from ? 'No days in this period' : 'No activity recorded'}
					description="Steps, energy and heart rate are aggregated by day, so a day with none of them does not appear."
				/>
			</Card>
		{:else}
			<p class={MICRO}>One row a day, from whichever source ranks highest for that date.</p>

			<div class="flex flex-col gap-3">
				{#each days as day (day.date)}
					<ActivityCard
						{day}
						userId={page.params.id ?? ''}
						providerLabel={label(day.source.provider)}
					/>
				{/each}
			</div>

			<CursorBar {nav} pagination={data.days.pagination} size={data.pageSize} />
		{/if}
	</div>
</div>
