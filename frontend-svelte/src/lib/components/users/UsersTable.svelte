<script lang="ts">
	import CopyableId from '$lib/components/ui/CopyableId.svelte';
	import SortableHeader from '$lib/components/ui/SortableHeader.svelte';
	import { formatDate } from '$lib/utils/datetime';
	import {
		usersQueryHref,
		withUsersQuery,
		type SortField,
		type UsersQuery
	} from '$lib/users/query';
	import type { SortOrder } from '$lib/lists/types';
	import type { User } from '$lib/users/types';
	import ConnectionBadges from './ConnectionBadges.svelte';
	import SyncCell from './SyncCell.svelte';
	import UserActions from './UserActions.svelte';
	import UserIdentity from './UserIdentity.svelte';

	let { users, query }: { users: User[]; query: UsersQuery } = $props();

	const head =
		'px-4 py-3 text-left text-[0.6875rem] font-semibold tracking-wide text-muted-foreground uppercase';

	const sortHref = (field: string, order: SortOrder) =>
		usersQueryHref(withUsersQuery(query, { sort: field as SortField, order }));

	// aria-sort belongs on the column header, not on the link inside it.
	const sortState = (field: string) =>
		query.sort === field ? (query.order === 'asc' ? 'ascending' : 'descending') : 'none';
</script>

{#snippet column(field: SortField, label: string)}
	<th scope="col" class={head} aria-sort={sortState(field)}>
		<SortableHeader {field} sort={query.sort} order={query.order} hrefFor={sortHref}>
			{label}
		</SortableHeader>
	</th>
{/snippet}

<table class="w-full border-collapse">
	<!-- Not sticky: the wrapper's overflow-x makes sticky anchor to the wrapper
	     rather than the viewport, which drops the header onto the first row. -->
	<thead class="border-b border-border bg-surface-muted/40">
		<tr>
			{@render column('name', 'User')}
			<th scope="col" class={head}>Connections</th>
			{@render column('last_synced_at', 'Last sync')}
			{@render column('created_at', 'Created')}
			<th scope="col" class={head}>ID</th>
			<th scope="col" class="{head} text-right">Actions</th>
		</tr>
	</thead>
	<tbody>
		{#each users as user (user.id)}
			<tr
				class="group relative border-b border-border/50 transition-colors hover:bg-surface-muted/40"
			>
				<td class="px-4 py-3"><UserIdentity {user} overlay /></td>
				<td class="px-4 py-3"><ConnectionBadges connections={user.connections} /></td>
				<td class="px-4 py-3"><SyncCell {user} /></td>
				<td class="px-4 py-3 text-sm whitespace-nowrap text-muted-foreground">
					{formatDate(user.created_at)}
				</td>
				<td class="px-4 py-3"><CopyableId value={user.id} label="user ID" /></td>
				<td class="px-4 py-3">
					<!-- Revealed on hover or keyboard focus so the row reads as data first. -->
					<div
						class="opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100"
					>
						<UserActions {user} />
					</div>
				</td>
			</tr>
		{/each}
	</tbody>
</table>
