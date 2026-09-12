<script lang="ts">
	import KeyRound from '@lucide/svelte/icons/key-round';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Hint from '$lib/components/ui/Hint.svelte';
	import { parseScopes, scopeLabel } from '$lib/connections/scopes';

	let { scope }: { scope: string | null } = $props();

	const scopes = $derived(parseScopes(scope));
</script>

<!-- A count beside the name rather than a row under it: the list is only ever
     read when something is missing, and a row cost every card its height. -->
{#if scopes.length > 0}
	<Hint label="{scopes.length} granted scopes" align="left">
		{#snippet trigger()}
			<Badge class="px-1.5 tabular-nums">
				<KeyRound size={11} aria-hidden="true" />
				{scopes.length}
			</Badge>
		{/snippet}

		<ul class="flex flex-col gap-0.5 font-mono">
			{#each scopes as entry (entry)}
				<li>{scopeLabel(entry)}</li>
			{/each}
		</ul>
	</Hint>
{/if}
