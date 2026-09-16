<script lang="ts">
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import Construction from '@lucide/svelte/icons/construction';
	import { tabLabel } from '$lib/users/tabs';
	import { page } from '$app/state';

	const label = $derived(tabLabel(page.params.tab ?? ''));
</script>

<Card>
	<EmptyState
		icon={Construction}
		title="{label} is not built yet"
		description="This tab is next in line. The Profile tab is complete."
	/>
</Card>
