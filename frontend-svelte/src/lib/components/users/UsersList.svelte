<script lang="ts">
	import type { UsersQuery } from '$lib/users/query';
	import type { User } from '$lib/users/types';
	import UserCard from './UserCard.svelte';
	import UsersTable from './UsersTable.svelte';

	let { users, query }: { users: User[]; query: UsersQuery } = $props();
</script>

<!-- Both are rendered and one is hidden by CSS. Choosing in JS instead would
     need the viewport width, which the server does not have. -->
<div class="hidden overflow-x-auto rounded-xl border border-border bg-surface md:block">
	<UsersTable {users} {query} />
</div>

<ul class="flex flex-col gap-3 md:hidden">
	{#each users as user (user.id)}
		<li><UserCard {user} /></li>
	{/each}
</ul>
