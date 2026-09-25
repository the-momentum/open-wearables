<script lang="ts">
	import Archive from '@lucide/svelte/icons/archive';
	import Database from '@lucide/svelte/icons/database';
	import HardDrive from '@lucide/svelte/icons/hard-drive';
	import Table from '@lucide/svelte/icons/table';
	import Activity from '@lucide/svelte/icons/activity';
	import ShareBar from '$lib/components/charts/ShareBar.svelte';
	import BetaTag from '$lib/components/ui/BetaTag.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import Figures from '$lib/components/ui/Figures.svelte';
	import { FOOTNOTE } from '$lib/components/ui/typography';
	import { archiveBytes, liveBytes } from '$lib/lifecycle/projection';
	import type { StorageEstimate } from '$lib/lifecycle/types';
	import { formatBytes, formatCompact, formatPercent } from '$lib/utils/format';

	let { storage }: { storage: StorageEstimate } = $props();

	const rows = (count: number) => `~${formatCompact(count)} rows`;
	const parts = (data: number, index: number) =>
		`${formatBytes(data)} + ${formatBytes(index)} indexes`;

	const figures = $derived([
		{
			icon: Activity,
			label: 'Live series',
			value: formatBytes(liveBytes(storage)),
			note: `${rows(storage.live_row_count)} · ${parts(storage.live_data_bytes, storage.live_index_bytes)}`
		},
		{
			icon: Archive,
			label: 'Archive',
			value: formatBytes(archiveBytes(storage)),
			note: `${rows(storage.archive_row_count)} · ${parts(storage.archive_data_bytes, storage.archive_index_bytes)}`
		},
		{ icon: Table, label: 'Other tables', value: formatBytes(storage.other_tables_bytes) },
		{ icon: Database, label: 'Whole database', value: formatBytes(storage.total_bytes) }
	]);

	// Where the bytes are, at a glance: on most installs the live series is
	// nearly all of it, which is the whole case for archiving.
	const shares = $derived([
		{ key: 'live', label: 'Live series', value: liveBytes(storage), shade: 'bg-primary' },
		{ key: 'archive', label: 'Archive', value: archiveBytes(storage), shade: 'bg-primary/45' },
		{
			key: 'other',
			label: 'Other tables',
			value: storage.other_tables_bytes,
			shade: 'bg-muted-foreground/30'
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

	<div class="flex flex-col gap-5">
		<Figures {figures} label="Storage by table" />
		<ShareBar
			parts={shares}
			format={(part, total) => `${formatBytes(part.value)} · ${formatPercent(part.value, total)}`}
		/>

		<p class={FOOTNOTE}>
			Row counts are Postgres's own planner estimate, not a count, and can trail far behind until
			the next ANALYZE — counting for real would mean scanning the table this page watches.
		</p>
	</div>
</Card>
