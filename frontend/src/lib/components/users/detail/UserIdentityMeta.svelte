<script lang="ts">
	import CopyableId from '$lib/components/ui/CopyableId.svelte';
	import type { User } from '$lib/users/types';
	import { formatDate, formatRelativeTime } from '$lib/utils/datetime';
	import { humanise } from '$lib/utils/text';

	let { user }: { user: User } = $props();
</script>

<!-- One line on a desktop; a phone gives the email and the sync lines of their own. -->
<div class="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
	{#if user.email}
		<span class="min-w-0 truncate text-secondary-foreground max-sm:basis-full">{user.email}</span>
	{/if}
	<CopyableId value={user.id} label="User ID" />
	<span>Created {formatDate(user.created_at)}</span>
	<span class="max-sm:basis-full">
		{#if user.last_synced_at}
			Synced {formatRelativeTime(user.last_synced_at)}
			{#if user.last_synced_provider}
				via {humanise(user.last_synced_provider)}
			{/if}
		{:else}
			Never synced
		{/if}
	</span>
</div>
