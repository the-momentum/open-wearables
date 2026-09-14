<script lang="ts">
	import { cn } from '$lib/utils/cn';
	import type { UserConnection } from '$lib/users/types';

	let { connections }: { connections: UserConnection[] | null } = $props();

	const STATUS_CLASS = {
		active: 'border-success/30 bg-success/10 text-success',
		expired: 'border-warning/30 bg-warning/10 text-warning',
		revoked: 'border-border bg-surface-muted text-muted-foreground'
	} as const;

	// Active first, so the badge that matters is not pushed off the end.
	const ordered = $derived(
		[...(connections ?? [])].sort((a, b) =>
			a.status === b.status ? a.provider.localeCompare(b.provider) : a.status === 'active' ? -1 : 1
		)
	);
</script>

{#if connections === null}
	<span class="text-xs text-muted-foreground/60">—</span>
{:else if ordered.length === 0}
	<span class="text-xs text-muted-foreground/60">No connections</span>
{:else}
	<ul class="flex flex-wrap gap-1">
		{#each ordered as connection (connection.provider)}
			<li
				title="{connection.provider}: {connection.status}"
				class={cn(
					'rounded-md border px-1.5 py-0.5 text-[0.6875rem] leading-none capitalize',
					STATUS_CLASS[connection.status]
				)}
			>
				{connection.provider}
			</li>
		{/each}
	</ul>
{/if}
