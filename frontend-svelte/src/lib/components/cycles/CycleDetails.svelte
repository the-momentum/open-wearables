<script lang="ts">
	import DeleteAction from '$lib/components/events/DeleteAction.svelte';
	import FieldGroups from '$lib/components/ui/FieldGroups.svelte';
	import { detailGroups } from '$lib/cycles/fields';
	import type { Cycle } from '$lib/cycles/types';

	let { cycle, ondelete }: { cycle: Cycle; ondelete: () => void } = $props();
</script>

<div class="flex flex-col gap-5 border-t border-border pt-4">
	<FieldGroups groups={detailGroups(cycle)} />

	<div class="flex justify-end border-t border-border pt-3">
		<DeleteAction label="Delete cycle" onclick={ondelete} />
	</div>
</div>
