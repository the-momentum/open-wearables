<script lang="ts">
	import ConnectionBadges from '$lib/components/users/ConnectionBadges.svelte';
	import SyncCell from '$lib/components/users/SyncCell.svelte';
	import UserIdentity from '$lib/components/users/UserIdentity.svelte';
	import { formatRelativeTime } from '$lib/utils/datetime';
	import type { User } from '$lib/users/types';

	let { users }: { users: User[] } = $props();
</script>

<!-- Sorted by when they were created. Sorting by last sync instead costs a
     correlated max() per user row in the whole table; the sync on the right is
     computed for these rows only, which is a different query. -->
<ul class="flex flex-col">
	{#each users as user (user.id)}
		<li
			class="relative flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-border py-2.5
				last:border-0"
		>
			<UserIdentity {user} overlay secondary="Joined {formatRelativeTime(user.created_at)}" />

			<!-- Fixed widths, not `auto`: a column sized to its own row's content
			     starts somewhere different on every line. Below `sm` the badges take a
			     row of their own rather than squeezing the name to nothing. -->
			<span class="order-last w-full sm:order-none sm:ml-auto sm:w-44 sm:shrink-0">
				<ConnectionBadges connections={user.connections} />
			</span>

			<span class="ml-auto w-28 shrink-0 text-right sm:ml-0"><SyncCell {user} /></span>
		</li>
	{/each}
</ul>
