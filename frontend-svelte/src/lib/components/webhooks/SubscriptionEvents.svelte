<script lang="ts">
	import { MICRO } from '$lib/components/ui/typography';
	import type { EventSummary } from '$lib/webhooks/events';

	let { groups }: { groups: EventSummary[] } = $props();

	const SHOWN = 4;
</script>

<!-- A chip per group, folded: the events themselves are one click away, in the
     card's own details, so nothing sits behind a "+ more" you cannot open. -->
{#each groups.slice(0, SHOWN) as group (group.label)}
	<span
		title={group.stray
			? group.items.map((item) => item.name).join('\n')
			: group.items.map((item) => item.label).join(', ') || group.label}
		class="inline-flex max-w-full items-center gap-1.5 rounded-md px-2 py-1 text-xs
			{group.stray ? 'bg-warning/12 text-warning' : 'bg-surface-muted text-foreground/90'}"
	>
		<span class="truncate">{group.label}</span>
		{#if group.stray}
			<!-- Something to edit out, so it wears the warning tone and says how many. -->
			<span class="shrink-0 tabular-nums">{group.items.length}</span>
		{:else if !group.whole}
			<!-- A part of a group says how big a part; a whole one needs no count. -->
			<span
				class="shrink-0 rounded bg-surface px-1 text-[10px] leading-4 text-muted-foreground tabular-nums"
			>
				{group.items.length}/{group.total}
			</span>
		{/if}
	</span>
{/each}
{#if groups.length > SHOWN}
	<span class={MICRO}>+{groups.length - SHOWN} groups</span>
{/if}
