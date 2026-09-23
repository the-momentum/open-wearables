<script lang="ts">
	import ExpandChevron from '$lib/components/ui/ExpandChevron.svelte';
	import { tagClass } from '$lib/components/ui/chip';
	import { MICRO, MONO, TEXT_LINK } from '$lib/components/ui/typography';
	import { cn } from '$lib/utils/cn';
	import { toggled, withAll } from '$lib/utils/collect';
	import { groupEvents, namesIn } from '$lib/webhooks/events';
	import type { EventType } from '$lib/webhooks/types';

	let { types, chosen = $bindable([]) }: { types: EventType[]; chosen?: string[] } = $props();

	const groups = $derived(groupEvents(types));
	let opened = $state<string[]>([]);

	const pickedIn = (names: string[]) => names.filter((name) => chosen.includes(name)).length;

	/**
	 * Every event in the family at once. Deliberately *not* what the group event
	 * does: `heart_rate.created` is its own subscription — one event covering the
	 * category — while its children are the granular ones. Making the parent a
	 * bulk selector would take that choice away.
	 */
	function setAll(names: string[], on: boolean) {
		chosen = withAll(chosen, names, on);
	}

	const chip = (on: boolean) => cn(tagClass(on), MONO);
</script>

<!-- Eighty names in one flat wall is a list nobody reads: each family folds, and
     a closed one still says how many of it are on. -->
<div class="flex flex-col divide-y divide-border rounded-lg border border-border">
	{#each groups as group (group.label)}
		{@const names = namesIn(group)}
		{@const picked = pickedIn(names)}
		{@const open = opened.includes(group.label)}

		<div class="flex flex-col">
			<button
				type="button"
				onclick={() => (opened = toggled(opened, group.label))}
				aria-expanded={open}
				class="flex items-center gap-2 px-3 py-2 text-left"
			>
				<ExpandChevron {open} />
				<span class="flex-1 text-xs font-medium text-foreground">{group.label}</span>
				<span class={MICRO}>{picked > 0 ? `${picked} of ${names.length}` : names.length}</span>
			</button>

			{#if open}
				<div class="flex flex-col gap-2 px-3 pt-1 pb-3">
					<button
						type="button"
						onclick={() => setAll(names, picked < names.length)}
						class="{TEXT_LINK} self-start"
					>
						{picked < names.length ? 'Select all' : 'Clear all'}
					</button>

					<div class="flex flex-wrap gap-1.5">
						{#if group.parent}
							<button
								type="button"
								onclick={() => (chosen = toggled(chosen, group.parent!.name))}
								aria-pressed={chosen.includes(group.parent.name)}
								title="One event covering the whole category, instead of the granular ones"
								class="{chip(chosen.includes(group.parent.name))} font-semibold"
							>
								{group.parent.name}
							</button>
						{/if}
						{#each group.events as event (event.name)}
							<button
								type="button"
								onclick={() => (chosen = toggled(chosen, event.name))}
								aria-pressed={chosen.includes(event.name)}
								title={event.description}
								class={chip(chosen.includes(event.name))}
							>
								{event.name}
							</button>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/each}
</div>
