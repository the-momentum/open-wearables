<script lang="ts">
	import CopyableId from '$lib/components/ui/CopyableId.svelte';
	import type { User } from '$lib/users/types';
	import ConnectionBadges from './ConnectionBadges.svelte';
	import SyncCell from './SyncCell.svelte';
	import UserActions from './UserActions.svelte';
	import UserIdentity from './UserIdentity.svelte';

	let { user }: { user: User } = $props();
</script>

<article
	class="relative rounded-xl border border-border bg-surface p-4 transition-colors
		hover:bg-surface-muted/40"
>
	<div class="flex items-start justify-between gap-2">
		<UserIdentity {user} overlay />
		<UserActions {user} />
	</div>

	<div class="mt-3 flex items-end justify-between gap-3">
		<div class="min-w-0">
			<ConnectionBadges connections={user.connections} />
			<div class="mt-2"><SyncCell {user} /></div>
		</div>
		<CopyableId value={user.id} label="user ID" />
	</div>
</article>
