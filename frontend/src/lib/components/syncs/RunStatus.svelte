<script lang="ts">
	import Badge from '$lib/components/ui/Badge.svelte';
	import { isRunning, statusTone } from '$lib/syncs/format';
	import { humanise } from '$lib/utils/text';

	let { run }: { run: { status: string; stage?: string } } = $props();
</script>

<!-- A running sync says where it is, since "in progress" says nothing new. -->
<Badge tone={statusTone(run.status)}>
	{humanise(isRunning(run.status) && run.stage ? run.stage : run.status)}
</Badge>
