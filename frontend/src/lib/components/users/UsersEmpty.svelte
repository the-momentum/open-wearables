<script lang="ts">
	import SearchX from '@lucide/svelte/icons/search-x';
	import Users from '@lucide/svelte/icons/users';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import type { UsersQuery } from '$lib/users/query';

	let { query }: { query: UsersQuery } = $props();

	const filtered = $derived(Boolean(query.search) || query.providers.length > 0);
	const title = $derived(
		query.search
			? `No users match “${query.search}”`
			: filtered
				? 'No users match these filters'
				: 'No users yet'
	);
</script>

<Card>
	<EmptyState icon={filtered ? SearchX : Users} {title} />
</Card>
