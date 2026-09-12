<script lang="ts">
	import type { UsersQuery } from '$lib/users/query';

	let { query }: { query: UsersQuery } = $props();
</script>

<p class="rounded-xl border border-border bg-surface px-4 py-10 text-center text-sm">
	{#if query.search}
		<span class="text-muted-foreground">No users match</span>
		<span class="font-medium">{query.search}</span>
	{:else if query.providers.length > 0}
		<span class="text-muted-foreground">No users match these filters.</span>
	{:else}
		<span class="text-muted-foreground">No users yet.</span>
	{/if}
</p>
