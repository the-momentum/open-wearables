<script lang="ts">
	import Badge from '$lib/components/ui/Badge.svelte';
	import Hint from '$lib/components/ui/Hint.svelte';
	import { connectionNote, connectionTone } from '$lib/connections/status';
	import { cn } from '$lib/utils/cn';
	import { humanise } from '$lib/utils/text';
	import type { UserConnection } from '$lib/users/types';

	let {
		connections,
		stacked = false
	}: {
		connections: UserConnection[] | null;
		/** One pill per line from `sm` up, for a narrow column beside a row's other cells. */
		stacked?: boolean;
	} = $props();

	// Active first, so the badge that matters is not pushed off the end.
	const ordered = $derived(
		[...(connections ?? [])].sort((a, b) =>
			a.status === b.status ? a.provider.localeCompare(b.provider) : a.status === 'active' ? -1 : 1
		)
	);
</script>

{#if connections === null}
	<span class="text-xs text-muted-foreground">-</span>
{:else if ordered.length === 0}
	<span class="text-xs text-muted-foreground">No connections</span>
{:else}
	<!-- The tint is the status, never the provider; colour alone cannot name it,
	     so the tooltip does. z-10 lifts it over the row-wide overlay link. -->
	<ul class={cn('flex flex-wrap gap-1', stacked && 'sm:flex-col sm:items-start')}>
		{#each ordered as connection (connection.provider)}
			{@const provider = humanise(connection.provider)}
			<li class="relative z-10">
				<Hint
					label="{provider}: {connection.status}"
					text={connectionNote(connection.status)}
					align="left"
				>
					{#snippet trigger()}
						<Badge tone={connectionTone(connection.status)}>{provider}</Badge>
					{/snippet}
				</Hint>
			</li>
		{/each}
	</ul>
{/if}
