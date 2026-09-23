<script lang="ts">
	import Badge from '$lib/components/ui/Badge.svelte';
	import { isRunning, statusTone } from '$lib/syncs/format';
	import type { SyncRunSummary } from '$lib/syncs/types';
	import { humanise } from '$lib/utils/text';

	let { run }: { run: Pick<SyncRunSummary, 'status' | 'stage'> } = $props();
</script>

<!-- A running sync says where it is, since "in progress" says nothing new. -->
<Badge tone={statusTone(run.status)}>
	{isRunning(run.status) ? humanise(run.stage) : humanise(run.status)}
</Badge>
