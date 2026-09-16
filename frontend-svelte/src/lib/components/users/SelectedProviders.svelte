<script lang="ts">
	import X from '@lucide/svelte/icons/x';
	import FilterChip from '$lib/components/ui/FilterChip.svelte';
	import type { Provider } from '$lib/server/providers';
	import {
		toggleProvider,
		usersQueryHref,
		withUsersQuery,
		type UsersQuery
	} from '$lib/users/query';

	let { query, providers }: { query: UsersQuery; providers: Provider[] } = $props();

	// Falls back to the raw name so a provider the backend no longer returns is
	// still visible and removable, rather than silently filtering in the dark.
	const chosen = $derived(
		query.providers.map(
			(name) => providers.find((provider) => provider.provider === name)?.name ?? name
		)
	);
</script>

<!-- Every href here comes from usersQueryHref, which calls resolve(). -->
<!-- eslint-disable svelte/no-navigation-without-resolve -->
{#if chosen.length > 0}
	<div class="flex flex-wrap items-center gap-1.5">
		{#each query.providers as provider, index (provider)}
			<FilterChip href={usersQueryHref(toggleProvider(query, provider))} selected>
				{chosen[index]}
			</FilterChip>
		{/each}

		<a
			href={usersQueryHref(withUsersQuery(query, { providers: [] }))}
			class="ml-1 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
		>
			<X size={13} aria-hidden="true" />
			Clear
		</a>
	</div>
{/if}
