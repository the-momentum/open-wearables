<script lang="ts">
	import { resolve } from '$app/paths';
	import { fullName } from '$lib/users/avatar';
	import type { User } from '$lib/users/types';
	import UserAvatar from './UserAvatar.svelte';

	let { user, overlay = false }: { user: User; overlay?: boolean } = $props();

	const name = $derived(fullName(user));
</script>

<div class="flex min-w-0 items-center gap-3">
	<UserAvatar {user} />

	<div class="min-w-0">
		<!-- `overlay` stretches this one link across the whole row, so the row is
		     clickable without JS and still reachable by keyboard as a link. -->
		<a
			href={resolve(`/users/${user.id}`)}
			class="block truncate text-sm font-medium transition-colors hover:text-primary
				{overlay ? 'after:absolute after:inset-0' : ''}"
		>
			{#if name}
				{name}
			{:else}
				<span class="text-muted-foreground/70 italic">Unnamed</span>
			{/if}
		</a>
		<span class="block truncate text-xs text-muted-foreground">{user.email ?? '—'}</span>
	</div>
</div>
