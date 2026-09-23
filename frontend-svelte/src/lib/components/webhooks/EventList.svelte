<script lang="ts">
	import { CAPTION, MICRO } from '$lib/components/ui/typography';
	import type { EventSummary } from '$lib/webhooks/events';

	let { groups }: { groups: EventSummary[] } = $props();
</script>

<div class="flex flex-col gap-2">
	<span class={MICRO}>Listens to</span>

	{#if groups.length === 0}
		<!-- An empty filter is a choice: it includes events the catalogue adds later. -->
		<p class="text-sm text-foreground/90">
			Every event, including ones added after this was created.
		</p>
	{:else}
		<dl class="grid grid-cols-[minmax(0,9rem)_1fr] gap-x-4 gap-y-1.5 text-sm">
			{#each groups as group (group.label)}
				<dt class="pt-0.5 {CAPTION}">{group.label}</dt>
				<dd class="flex min-w-0 flex-wrap gap-x-2 gap-y-0.5 text-foreground/90">
					{#if group.groupEvent}
						<!-- One event for the lot, not one per series: it says so. -->
						<span title="{group.groupEvent.name}: {group.groupEvent.description}">
							the whole group
						</span>
					{/if}
					{#each group.items as item, index (item.name)}
						{#if index > 0 || group.groupEvent}<span
								aria-hidden="true"
								class="text-muted-foreground/60">·</span
							>{/if}
						<span title="{item.name}{item.description ? `: ${item.description}` : ''}">
							{item.label}
						</span>
					{/each}
				</dd>
			{/each}
		</dl>
	{/if}
</div>
