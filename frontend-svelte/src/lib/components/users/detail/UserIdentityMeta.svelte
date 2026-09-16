<script lang="ts">
	import CopyableId from '$lib/components/ui/CopyableId.svelte';
	import type { UserDetail } from '$lib/users/types';
	import { formatDate, formatRelativeTime } from '$lib/utils/datetime';
	import { humanise } from '$lib/utils/text';

	let { user }: { user: UserDetail } = $props();
</script>

<div
	class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground [&>*]:after:mx-2 [&>*]:after:text-border [&>*:not(:last-child)]:after:content-['·']"
>
	{#if user.email}
		<span class="text-foreground/80">{user.email}</span>
	{/if}
	<span><CopyableId value={user.id} label="User ID" /></span>
	<span>Created {formatDate(user.created_at)}</span>
	<span>
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
