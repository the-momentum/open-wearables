<script lang="ts">
	import Database from '@lucide/svelte/icons/database';
	import HardDrive from '@lucide/svelte/icons/hard-drive';
	import Layers from '@lucide/svelte/icons/layers';
	import Table from '@lucide/svelte/icons/table';
	import Activity from '@lucide/svelte/icons/activity';
	import ShareBar from '$lib/components/charts/ShareBar.svelte';
	import BetaTag from '$lib/components/ui/BetaTag.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import { ICON } from '$lib/components/ui/icon';
	import { MICRO } from '$lib/components/ui/typography';
	import { aggregateBytes, liveBytes } from '$lib/lifecycle/projection';
	import type { StorageEstimate } from '$lib/lifecycle/types';
	import { formatBytes, formatCompact } from '$lib/utils/format';

	let { storage }: { storage: StorageEstimate } = $props();

	// What a table is made of: its planner row estimate, its data, its indexes.
	const details = (rows: number, data: number, index: number) => [
		`~${formatCompact(rows)} rows`,
		formatBytes(data),
		`+ ${formatBytes(index)} indexes`
	];

	const figures = $derived([
		{
			icon: Activity,
			label: 'Live series',
			value: formatBytes(liveBytes(storage)),
			details: details(storage.live_row_count, storage.live_data_bytes, storage.live_index_bytes)
		},
		{
			icon: Layers,
			label: 'Aggregates',
			value: formatBytes(aggregateBytes(storage)),
			details: details(
				storage.aggregate_row_count,
				storage.aggregate_data_bytes,
				storage.aggregate_index_bytes
			)
		},
		{ icon: Table, label: 'Other tables', value: formatBytes(storage.other_tables_bytes) },
		{ icon: Database, label: 'Whole database', value: formatBytes(storage.total_bytes) }
	]);

	// Where the bytes are, at a glance: on most installs the live series is
	// nearly all of it, which is the whole case for rolling up and deleting.
	const shares = $derived([
		{ key: 'live', label: 'Live series', value: liveBytes(storage), shade: 'bg-primary-soft' },
		{
			key: 'aggregate',
			label: 'Aggregates',
			value: aggregateBytes(storage),
			shade: 'bg-primary/40'
		},
		{
			key: 'other',
			label: 'Other tables',
			value: storage.other_tables_bytes,
			shade: 'bg-surface-strong'
		}
	]);
</script>

<Card
	icon={HardDrive}
	title="Storage"
	description="What each part of the database takes on disk, indexes included."
>
	{#snippet action()}
		<BetaTag />
	{/snippet}

	<div class="flex flex-col gap-4">
		<dl aria-label="Storage by table" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 lg:gap-3">
			{#each figures as figure (figure.label)}
				<div class="flex items-start gap-3">
					<span
						aria-hidden="true"
						class="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-foreground"
					>
						<figure.icon size={ICON.sm} />
					</span>
					<!-- dt before dd, as a dl wants; the figure is lifted above its name. -->
					<div class="flex min-w-0 flex-col gap-1">
						<dt class="text-xs text-secondary-foreground">{figure.label}</dt>
						<dd class="order-first text-xl font-medium text-foreground tabular-nums sm:text-2xl">
							{figure.value}
						</dd>
						{#if figure.details}
							<dd class="flex flex-wrap gap-x-2 sm:flex-col sm:gap-0.5 {MICRO}">
								{#each figure.details as detail (detail)}<span>{detail}</span>{/each}
							</dd>
						{/if}
					</div>
				</div>
			{/each}
		</dl>

		<ShareBar parts={shares} value={(part) => formatBytes(part.value)} />

		<p class={MICRO}>
			Row counts are Postgres's own planner estimate, not a count, and can trail far behind until
			the next ANALYZE - counting for real would mean scanning the table this page watches.
		</p>
	</div>
</Card>
