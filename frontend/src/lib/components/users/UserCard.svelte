<script lang="ts">
	import CopyableId from '$lib/components/ui/CopyableId.svelte';
	import type { User } from '$lib/users/types';
	import { formatDate } from '$lib/utils/datetime';
	import ConnectionBadges from './ConnectionBadges.svelte';
	import SyncCell from './SyncCell.svelte';
	import UserActions from './UserActions.svelte';
	import UserIdentity from './UserIdentity.svelte';

	let { user }: { user: User } = $props();
</script>

<!-- A row of the phone's list, which draws the frame and the rules between. -->
<article class="relative flex flex-col gap-2 px-4 py-3.5">
	<div class="flex items-start justify-between gap-2">
		<UserIdentity {user} overlay />
		<UserActions {user} menu />
	</div>

	<div class="flex items-start justify-between gap-3">
		<ConnectionBadges connections={user.connections} />
		<div class="shrink-0 text-right"><SyncCell {user} /></div>
	</div>

	<div class="flex items-center gap-2">
		<span class="text-sm text-muted-foreground">{formatDate(user.created_at)}</span>
		<CopyableId value={user.id} label="user ID" />
	</div>
</article>
