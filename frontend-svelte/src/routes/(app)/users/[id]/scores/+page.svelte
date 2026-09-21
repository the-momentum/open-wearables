<script lang="ts">
	import Trophy from '@lucide/svelte/icons/trophy';
	import { page } from '$app/state';
	import { tones } from '$lib/charts/palette';
	import FilterBar from '$lib/components/filters/FilterBar.svelte';
	import CategoryFilter from '$lib/components/scores/CategoryFilter.svelte';
	import ScoreCard from '$lib/components/scores/ScoreCard.svelte';
	import ScoreTrends from '$lib/components/scores/ScoreTrends.svelte';
	import Caption from '$lib/components/ui/Caption.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import Pagination from '$lib/components/ui/Pagination.svelte';
	import { periodParams } from '$lib/filters/period';
	import type { PageSize } from '$lib/lists/pagination';
	import { providerLabel } from '$lib/providers/labels';
	import { groupByDay } from '$lib/scores/group';
	import { categoriesIn, categoryTrends, providersIn } from '$lib/scores/trends';
	import type { HealthScore } from '$lib/scores/types';
	import { resource } from '$lib/utils/resource.svelte';
	import { withParams } from '$lib/utils/url';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	// Any filter change returns to page one: page five of the old list would
	// otherwise answer for page one of the new one.
	const hrefFor = (changes: Record<string, string | null>) =>
		withParams(page.url, { page: null, ...changes });
	const pageHref = (at: number) => withParams(page.url, { page: at === 1 ? null : String(at) });
	const sizeHref = (size: PageSize) => hrefFor({ size: String(size) });

	const label = (entry: string) => providerLabel(data.providers, entry);

	// The page owns this fetch rather than the chart, because two things read it:
	// the trends, and the list of categories there is anything to choose between.
	// Only the period, not the whole query: refetching every trend to narrow the
	// list below would throw away the chart the reader is looking at.
	const history = resource<{ scores: HealthScore[]; truncated: boolean }>(
		() => `/users/${page.params.id}/scores/trends?${periodParams(data.period)}`
	);

	const trends = $derived(categoryTrends(history.current?.scores ?? [], label));
	const categories = $derived(categoriesIn(trends, data.category));

	// Assigned once for the whole page: the tiles and a card's own curve have to
	// agree on which colour a provider is.
	const colourFor = $derived(tones(providersIn(trends)));

	const days = $derived(groupByDay(data.scores.data));
</script>

<div class="flex flex-col gap-6">
	<!-- No provider filter: a score is only interesting next to the other
	     providers' answer for the same day, and OW's own score is one of those.
	     The chart's legend hides a line without losing the comparison. -->
	<FilterBar period={data.period} {hrefFor} providers={[]} labelFor={label} selected="">
		<CategoryFilter category={data.category} {categories} {hrefFor} />
	</FilterBar>

	<div class="flex flex-col gap-5 border-t border-border pt-6">
		<ScoreTrends
			{trends}
			settled={history.settled}
			truncated={history.current?.truncated ?? false}
			category={data.category}
			{hrefFor}
			{colourFor}
		/>

		{#if days.length === 0}
			<Card>
				<EmptyState
					icon={Trophy}
					title={data.narrowed ? 'No scores match these filters' : 'No scores recorded'}
					description={data.narrowed
						? 'Widen the period, or choose every category.'
						: 'Scores come from the providers that compute them, and from Open Wearables itself.'}
				/>
			</Card>
		{:else}
			<div class="flex flex-col gap-2">
				<Caption>A day at a time</Caption>
				<div class="flex flex-col gap-3">
					{#each days as day (day.day)}
						<ScoreCard {day} labelFor={label} {colourFor} />
					{/each}
				</div>
			</div>

			<!-- Counted in days, because a card is a day: the endpoint pages by
			     record, and a page of twenty records is two cards for a provider that
			     scores every half hour. -->
			<Pagination
				page={data.page}
				size={data.perPage}
				total={data.total}
				noun="days"
				previousHref={data.page > 1 ? pageHref(data.page - 1) : null}
				nextHref={data.page < data.pages ? pageHref(data.page + 1) : null}
				hrefFor={pageHref}
				sizeHrefFor={sizeHref}
			/>
		{/if}
	</div>
</div>
