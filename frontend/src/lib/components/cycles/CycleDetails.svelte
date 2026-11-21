<script lang="ts">
	import EventDetails from '$lib/components/events/EventDetails.svelte';
	import FieldGroups from '$lib/components/ui/FieldGroups.svelte';
	import { detailGroups } from '$lib/cycles/fields';
	import type { Cycle } from '$lib/cycles/types';

	let { cycle, ondelete }: { cycle: Cycle; ondelete: () => void } = $props();
</script>

<EventDetails deleteLabel="Delete cycle" {ondelete}>
	<FieldGroups groups={detailGroups(cycle)} />
</EventDetails>
