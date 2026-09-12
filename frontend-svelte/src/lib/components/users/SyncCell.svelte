<script lang="ts">
	import { formatRelativeTime } from '$lib/utils/datetime';
	import type { User } from '$lib/users/types';

	let { user }: { user: User } = $props();
</script>

{#if user.last_synced_at}
	<span class="text-sm whitespace-nowrap text-foreground/80">
		{formatRelativeTime(user.last_synced_at)}
	</span>
	{#if user.last_synced_provider}
		<!-- capitalize only the provider: on the whole string it also lifts "via". -->
		<span class="block text-xs text-muted-foreground/70">
			via <span class="capitalize">{user.last_synced_provider}</span>
		</span>
	{/if}
{:else}
	<span class="text-sm text-muted-foreground/60">Never</span>
{/if}
