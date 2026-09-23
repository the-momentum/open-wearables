<script lang="ts">
	import Archive from '@lucide/svelte/icons/archive';
	import BetaTag from '$lib/components/ui/BetaTag.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
</script>

<Card
	icon={Archive}
	title="Data lifecycle"
	description="Archive and deletion windows for stored health data."
>
	{#snippet action()}
		<BetaTag />
	{/snippet}

	<EmptyState
		icon={Archive}
		title="Not in this dashboard yet"
		description="Archival and retention still live in the old dashboard. The rules are still running on your data — nothing here turns them off."
	/>
</Card>
