<script lang="ts">
	import CopyableId from '$lib/components/ui/CopyableId.svelte';
	import SortableHeader from '$lib/components/ui/SortableHeader.svelte';
	import { LIST_ROW, TABLE_CELL, TABLE_HEAD, TABLE_HEADER } from '$lib/components/ui/table';
	import { cn } from '$lib/utils/cn';
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

	const sortHref = (field: string, order: SortOrder) =>
		usersQueryHref(withUsersQuery(query, { sort: field as SortField, order }));

	// aria-sort belongs on the column header, not on the link inside it.
	const sortState = (field: string) =>
		query.sort === field ? (query.order === 'asc' ? 'ascending' : 'descending') : 'none';
</script>

<!-- Fixed widths, as the design's: the user column takes what is left. -->
{#snippet column(field: SortField, label: string, width?: string)}
	<th scope="col" class={cn(TABLE_HEADER, width)} aria-sort={sortState(field)}>
		<SortableHeader {field} sort={query.sort} order={query.order} hrefFor={sortHref}>
			{label}
		</SortableHeader>
	</th>
{/snippet}

<table class="w-full border-collapse">
	<thead class={TABLE_HEAD}>
		<tr>
			{@render column('name', 'User')}
			<th scope="col" class="{TABLE_HEADER} w-45">Connections</th>
			{@render column('last_synced_at', 'Last sync', 'w-36')}
			{@render column('created_at', 'Created', 'w-34')}
			<th scope="col" class="{TABLE_HEADER} w-36">ID</th>
			<th scope="col" class="{TABLE_HEADER} w-36 text-right">Actions</th>
		</tr>
	</thead>
	<tbody>
		{#each users as user (user.id)}
			<tr class="group relative {LIST_ROW}">
				<td class={TABLE_CELL}><UserIdentity {user} overlay /></td>
				<td class={TABLE_CELL}><ConnectionBadges connections={user.connections} /></td>
				<td class={TABLE_CELL}><SyncCell {user} /></td>
				<td class="{TABLE_CELL} text-sm whitespace-nowrap text-muted-foreground">
					{formatDate(user.created_at)}
				</td>
				<td class={TABLE_CELL}><CopyableId value={user.id} label="user ID" /></td>
				<td class={TABLE_CELL}>
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
