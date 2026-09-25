<script lang="ts">
	import Users from '@lucide/svelte/icons/users';
	import ShareBar from '$lib/components/charts/ShareBar.svelte';
	import NewestUsers from '$lib/components/dashboard/NewestUsers.svelte';
	import StatTile from '$lib/components/dashboard/StatTile.svelte';
	import CountRanking from '$lib/components/summary/CountRanking.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import { eventMix, providerUse, reachParts, statTiles } from '$lib/dashboard/stats';
	import { providerLabel } from '$lib/providers/labels';
	import { formatShare } from '$lib/utils/format';
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
	<div class="flex flex-col gap-4">
		<!-- One column on a phone, two on a tablet, four on a desktop. -->
		<section aria-label="Platform totals" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
			{#each statTiles(info) as tile (tile.label)}
				<StatTile {...tile} />
			{/each}
		</section>

		<div class="grid gap-4 lg:grid-cols-2">
			<Card title="Connections" description="How much of the user base is sending anything">
				<div class="flex flex-col gap-5">
					<ShareBar
						parts={reachParts(info)}
						format={(part, total) => formatShare(part.value, total)}
					/>

					<!-- A count and its share of every live connection: 480 means little
					     without knowing whether that is half the estate or a tenth. -->
					<CountRanking
						counts={providerUse(info)}
						labelFor={label}
						format={(count) => formatShare(count, info.active_conn.count)}
					/>
				</div>
			</Card>

			<Card title="Event records" description="Every session and cycle stored, by kind">
				<CountRanking counts={eventMix(info)} />
			</Card>
		</div>

		<Card title="Newest users">
			<NewestUsers users={data.users} />
		</Card>
	</div>
{/if}
