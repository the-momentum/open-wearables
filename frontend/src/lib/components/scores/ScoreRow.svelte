<script lang="ts">
	import Caption from '$lib/components/ui/Caption.svelte';
	import { categorySpec } from '$lib/scores/categories';
	import type { CategoryScores } from '$lib/scores/group';
	import ProviderScore from './ProviderScore.svelte';

	let { scores, labelFor }: { scores: CategoryScores; labelFor: (provider: string) => string } =
		$props();

	const spec = $derived(categorySpec(scores.category));
</script>

<!-- The measure on the left at a fixed width so a column of them can be scanned
     down the card, and its providers to the right of it. -->
<div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-4">
	<Caption icon={spec.icon} class="sm:w-28 sm:shrink-0">{spec.label}</Caption>
	<dl class="flex min-w-0 flex-wrap items-center gap-x-6 gap-y-1.5">
		{#each scores.providers as reading (reading.provider)}
			<ProviderScore {reading} {labelFor} />
		{/each}
	</dl>
</div>
