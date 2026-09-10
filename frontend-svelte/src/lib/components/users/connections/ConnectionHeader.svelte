<script lang="ts">
	import Badge from '$lib/components/ui/Badge.svelte';
	import ProviderMark from '$lib/components/providers/ProviderMark.svelte';
	import { connectionTone } from '$lib/connections/status';
	import type { Connection } from '$lib/connections/types';
	import { formatRelativeTime } from '$lib/utils/datetime';
	import { humanise } from '$lib/utils/text';
	import ConnectionMenu from './ConnectionMenu.svelte';
	import ScopeBadge from './ScopeBadge.svelte';

	let {
		connection,
		label,
		onrevoke,
		onpurge
	}: { connection: Connection; label: string; onrevoke: () => void; onpurge: () => void } =
		$props();
</script>

<div class="flex items-start justify-between gap-3">
	<div class="flex min-w-0 items-center gap-3">
		<ProviderMark provider={connection.provider} {label} />
		<div class="min-w-0">
			<!-- div, not p: the scope bubble holds a <ul>, which a <p> may not. -->
			<div class="flex min-w-0 items-center gap-2">
				<span class="truncate text-sm font-medium text-foreground">{label}</span>
				<ScopeBadge scope={connection.scope} />
			</div>
			<p class="text-xs text-muted-foreground">
				Synced {formatRelativeTime(connection.last_synced_at)}
			</p>
		</div>
	</div>

	<div class="flex shrink-0 items-center gap-2">
		<Badge tone={connectionTone(connection.status)}>{humanise(connection.status)}</Badge>
		<ConnectionMenu {label} {onrevoke} {onpurge} />
	</div>
</div>
