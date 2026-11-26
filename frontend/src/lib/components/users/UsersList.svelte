<script lang="ts">
	import { LIST_FRAME, LIST_ROW } from '$lib/components/ui/table';
	import type { UsersQuery } from '$lib/users/query';
	import type { User } from '$lib/users/types';
	import UserCard from './UserCard.svelte';
	import UsersTable from './UsersTable.svelte';

	let { users, query }: { users: User[]; query: UsersQuery } = $props();
</script>

<!-- Both are rendered and one is hidden by CSS. Choosing in JS instead would
     need the viewport width, which the server does not have. -->
<div class="hidden overflow-x-auto md:block {LIST_FRAME}">
	<UsersTable {users} {query} />
</div>

<ul class="overflow-hidden md:hidden {LIST_FRAME}">
	{#each users as user (user.id)}
		<li class={LIST_ROW}><UserCard {user} /></li>
	{/each}
</ul>
