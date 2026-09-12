<script lang="ts">
	import SlidersHorizontal from '@lucide/svelte/icons/sliders-horizontal';
	import { goto } from '$app/navigation';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import ToggleChip from '$lib/components/ui/ToggleChip.svelte';
	import type { Provider } from '$lib/server/providers';
	import { usersQueryHref, withUsersQuery, type UsersQuery } from '$lib/users/query';

	let { query, providers }: { query: UsersQuery; providers: Provider[] } = $props();

	let open = $state(false);
	// Selection is local until applied, so several providers can be picked in one
	// visit — and one navigation, not one per chip.
	let draft = $state<string[]>([]);

	function show() {
		draft = [...query.providers];
		open = true;
	}

	function toggle(provider: string) {
		draft = draft.includes(provider)
			? draft.filter((name) => name !== provider)
			: [...draft, provider].sort();
	}

	function apply() {
		open = false;
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- usersQueryHref resolves
		goto(usersQueryHref(withUsersQuery(query, { providers: draft })));
	}
</script>

<Button
	variant="outline"
	onclick={show}
	aria-haspopup="dialog"
	aria-expanded={open}
	class="w-full px-3"
>
	<SlidersHorizontal size={15} aria-hidden="true" />
	Provider
	{#if query.providers.length > 0}
		<Badge tone="info" class="px-1.5 tabular-nums">{query.providers.length}</Badge>
	{/if}
</Button>

<Sheet bind:open title="Filter by provider">
	<div class="flex max-h-[50dvh] flex-wrap gap-1.5 overflow-y-auto px-4 pb-3">
		{#each providers as provider (provider.provider)}
			<ToggleChip
				pressed={draft.includes(provider.provider)}
				onclick={() => toggle(provider.provider)}
			>
				{provider.name}
			</ToggleChip>
		{/each}
	</div>

	<div class="flex items-center justify-between gap-2 border-t border-border/60 px-4 pt-3">
		<button
			type="button"
			onclick={() => (draft = [])}
			disabled={draft.length === 0}
			class="text-sm text-muted-foreground hover:text-foreground disabled:opacity-40"
		>
			Clear all
		</button>
		<Button onclick={apply}>Apply</Button>
	</div>
</Sheet>
