<script lang="ts">
	import { TINY } from '$lib/components/ui/typography';
	import { cn } from '$lib/utils/cn';
	import type { UserConnection } from '$lib/users/types';

	let { connections }: { connections: UserConnection[] | null } = $props();

	// Active is the normal state and gets no mark; a dot flags only what needs attention.
	const DOT = {
		active: null,
		expired: 'bg-warning',
		revoked: 'bg-muted-foreground'
	} as const;

	// Active first, so the badge that matters is not pushed off the end.
	const ordered = $derived(
		[...(connections ?? [])].sort((a, b) =>
			a.status === b.status ? a.provider.localeCompare(b.provider) : a.status === 'active' ? -1 : 1
		)
	);
</script>

{#if connections === null}
	<span class="text-xs text-muted-foreground/60">-</span>
{:else if ordered.length === 0}
	<span class="text-xs text-muted-foreground/60">No connections</span>
{:else}
	<ul class="flex flex-wrap gap-1">
		{#each ordered as connection (connection.provider)}
			{@const dot = DOT[connection.status]}
			<li
				title="{connection.provider}: {connection.status}"
				class={cn(
					'inline-flex items-center gap-1 rounded-md border border-border px-1.5 py-0.5 leading-none text-secondary-foreground capitalize',
					TINY
				)}
			>
				{#if dot}
					<span aria-hidden="true" class={cn('size-1.5 shrink-0 rounded-full', dot)}></span>
					<span class="sr-only">{connection.status}:</span>
				{/if}
				{connection.provider}
			</li>
		{/each}
	</ul>
{/if}
