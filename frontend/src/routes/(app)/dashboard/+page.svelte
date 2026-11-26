<script lang="ts">
	import Users from '@lucide/svelte/icons/users';
	import DonutChart from '$lib/components/charts/DonutChart.svelte';
	import ShareBar from '$lib/components/charts/ShareBar.svelte';
	import NewestUsers from '$lib/components/dashboard/NewestUsers.svelte';
	import StatTile from '$lib/components/dashboard/StatTile.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import { providerUse, reachParts, statTiles } from '$lib/dashboard/stats';
	import { providerLabel } from '$lib/providers/labels';
	import { formatNumber } from '$lib/utils/format';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const info = $derived(data.info);
	const label = (provider: string) => providerLabel(data.providers, provider);
</script>

{#if info.total_users.count === 0}
	<Card>
		<EmptyState
			icon={Users}
			title="Nothing to show yet"
			description="Everything here counts users, their connections, and what those connections have sent."
		/>
	</Card>
{:else}
	<div class="flex flex-col gap-3 sm:gap-4">
		<!-- One shared band on a phone; separate tiles from two columns up. -->
		<section
			aria-label="Platform totals"
			class="grid gap-1 rounded-lg border border-border bg-surface p-1 sm:grid-cols-2 sm:gap-4
			sm:border-0 sm:bg-transparent sm:p-0 lg:grid-cols-4"
		>
			{#each statTiles(info) as tile (tile.label)}
				<StatTile {...tile} />
			{/each}
		</section>

		<div class="grid gap-3 sm:gap-4 lg:grid-cols-2">
			<!-- The design's height; the ring centres in what the bar leaves. -->
			<Card
				title="Connections"
				description="How much of the user base is sending anything"
				class="flex flex-col lg:min-h-105"
				bodyClass="flex flex-1 flex-col gap-6 sm:gap-5"
			>
				<ShareBar parts={reachParts(info)} value={(part) => formatNumber(part.value)} />

				<!-- Shares of every live connection, not of the six the backend names:
				     the rest is drawn as "Other", so the ring adds up to the total. -->
				<div class="flex flex-1 flex-col justify-center">
					<DonutChart
						parts={providerUse(info, label)}
						total={info.active_conn.count}
						caption="connections"
						label="Connections per provider"
					/>
				</div>
			</Card>

			<!-- Beside the connections it takes their height and scrolls: `contain-size`
			     keeps the list's own length out of the row's. -->
			<Card
				title="Newest users"
				class="flex flex-col lg:contain-size"
				bodyClass="min-h-0 flex-1 overflow-y-auto py-1 sm:py-1"
			>
				<NewestUsers users={data.users} />
			</Card>
		</div>
	</div>
{/if}
