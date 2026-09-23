<script lang="ts">
	import Sprout from '@lucide/svelte/icons/sprout';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
</script>

<Card
	icon={Sprout}
	title="Seed data"
	description="Generate synthetic users and health data for testing."
>
	<EmptyState
		icon={Sprout}
		title="Not in this dashboard yet"
		description="Seeding still lives in the old dashboard."
	/>
</Card>
