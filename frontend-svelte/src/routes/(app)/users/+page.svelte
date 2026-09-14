<script lang="ts">
	import Pagination from '$lib/components/ui/Pagination.svelte';
	import SearchField from '$lib/components/ui/SearchField.svelte';
	import AddUserButton from '$lib/components/users/AddUserButton.svelte';
	import ProviderFilter from '$lib/components/users/ProviderFilter.svelte';
	import SelectedProviders from '$lib/components/users/SelectedProviders.svelte';
	import DeleteUserDialog from '$lib/components/users/DeleteUserDialog.svelte';
	import UserFormDialog from '$lib/components/users/UserFormDialog.svelte';
	import UsersEmpty from '$lib/components/users/UsersEmpty.svelte';
	import UsersList from '$lib/components/users/UsersList.svelte';
	import type { PageSize } from '$lib/lists/pagination';
	import { usersQueryHref, withPageSize, withUsersQuery } from '$lib/users/query';
	import { setRowActions } from '$lib/users/row-actions';
	import type { User } from '$lib/users/types';
	import type { ActionData, PageData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	// One dialog of each kind for the whole page, not one per row. Openness is
	// separate from the subject so closing does not have to null the subject.
	let creating = $state(false);
	let editing = $state<User | null>(null);
	let editOpen = $state(false);
	let deleting = $state<User | null>(null);
	let deleteOpen = $state(false);

	setRowActions({
		edit: (user) => {
			editing = user;
			editOpen = true;
		},
		remove: (user) => {
			deleting = user;
			deleteOpen = true;
		}
	});

	const messageFor = (action: string) => (form?.action === action ? form.message : undefined);

	const searchHref = (search: string) => usersQueryHref(withUsersQuery(data.query, { search }));
	const pageHref = (page: number) => usersQueryHref(withUsersQuery(data.query, { page }));
	const sizeHref = (size: PageSize) => usersQueryHref(withPageSize(data.query, size));
</script>

{#snippet pager(position: 'above' | 'below')}
	<Pagination
		page={data.users}
		hrefFor={pageHref}
		sizeHrefFor={sizeHref}
		label="Pagination {position} the list"
	/>
{/snippet}

<div class="flex flex-col gap-4">
	<div class="flex flex-col gap-3 sm:flex-row sm:items-center">
		<div class="flex-1">
			<SearchField
				value={data.query.search}
				hrefFor={searchHref}
				label="Search users"
				placeholder="Search by name, email or ID"
				hidden={{ sort: data.query.sort, order: data.query.order }}
			/>
		</div>
		<!-- Side by side on a phone: three stacked rows would push the list
		     below the fold. -->
		<div class="flex gap-2">
			<div class="flex-1 sm:flex-none">
				<ProviderFilter query={data.query} providers={data.providers} />
			</div>
			<div class="flex-1 sm:flex-none">
				<AddUserButton onclick={() => (creating = true)} />
			</div>
		</div>
	</div>

	<SelectedProviders query={data.query} providers={data.providers} />

	{@render pager('above')}

	{#if data.users.items.length === 0}
		<UsersEmpty query={data.query} />
	{:else}
		<UsersList users={data.users.items} query={data.query} />
	{/if}

	{@render pager('below')}
</div>

<UserFormDialog bind:open={creating} message={messageFor('create')} />

<UserFormDialog bind:open={editOpen} user={editing} message={messageFor('update')} />

<DeleteUserDialog bind:open={deleteOpen} user={deleting} message={messageFor('delete')} />
