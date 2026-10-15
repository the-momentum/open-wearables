<script lang="ts">
	import Heart from '@lucide/svelte/icons/heart';
	import { page } from '$app/state';
	import CycleCard from '$lib/components/cycles/CycleCard.svelte';
	import CycleSummary from '$lib/components/cycles/CycleSummary.svelte';
	import PhaseLegend from '$lib/components/cycles/PhaseLegend.svelte';
	import CursorBar from '$lib/components/events/CursorBar.svelte';
	import DeleteEventDialog from '$lib/components/events/DeleteEventDialog.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import { cycleDays } from '$lib/cycles/phases';
	import type { Cycle } from '$lib/cycles/types';
	import { cursorHrefs } from '$lib/lists/cursor';
	import { providerLabel } from '$lib/providers/labels';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const nav = $derived(cursorHrefs(page.url));
	const cycles = $derived(data.cycles.data);

	// One scale for the whole page: bars drawn to their own length would make a
	// twenty-six day cycle look the same size as a thirty-one day one.
	const days = $derived(Math.max(...cycles.map((cycle) => cycleDays(cycle) ?? 0), 1));

	// One dialog for the page, and the subject is separate from openness so
	// closing does not have to null it mid-transition.
	let removing = $state<Cycle | null>(null);
	let removeOpen = $state(false);
</script>

<div class="flex flex-col gap-5">
	<CycleSummary userId={page.params.id ?? ''} />

	{#if cycles.length === 0}
		<Card>
			<EmptyState
				icon={Heart}
				title="No cycles recorded"
				description="Cycle tracking has to be switched on in the provider's own app before anything is sent."
			/>
		</Card>
	{:else}
		<div class="flex flex-col gap-3 border-t border-border pt-5">
			<PhaseLegend />

			<div class="flex flex-col gap-3">
				{#each cycles as cycle (cycle.id)}
					<CycleCard
						{cycle}
						{days}
						providerLabel={providerLabel(data.providers, cycle.source.provider)}
						ondelete={() => {
							removing = cycle;
							removeOpen = true;
						}}
					/>
				{/each}
			</div>

			<CursorBar {nav} pagination={data.cycles.pagination} size={data.pageSize} />
		</div>
	{/if}
</div>

<DeleteEventDialog
	bind:open={removeOpen}
	noun="cycle"
	action="?/deleteCycle"
	field="cycle"
	id={removing?.id ?? ''}
/>
