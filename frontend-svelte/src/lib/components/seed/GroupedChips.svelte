<script lang="ts">
	import { tagClass } from '$lib/components/ui/chip';
	import { CAPTION, TEXT_LINK } from '$lib/components/ui/typography';
	import { toggled, withAll } from '$lib/utils/collect';

	export type ChipGroup = { label: string; items: { id: string; label: string }[] };

	let { groups, chosen = $bindable([]) }: { groups: ChipGroup[]; chosen?: string[] } = $props();

	const ids = (group: ChipGroup) => group.items.map((item) => item.id);
	const allOn = (group: ChipGroup) => ids(group).every((id) => chosen.includes(id));

	const setGroup = (group: ChipGroup, on: boolean) => (chosen = withAll(chosen, ids(group), on));
</script>

<div class="flex flex-col gap-3">
	{#each groups as group (group.label)}
		<div class="flex flex-col gap-1.5">
			<div class="flex items-center gap-2">
				<span class={CAPTION}>{group.label}</span>
				<button type="button" onclick={() => setGroup(group, !allOn(group))} class={TEXT_LINK}>
					{allOn(group) ? 'none' : 'all'}
				</button>
			</div>
			<div class="flex flex-wrap gap-1.5">
				{#each group.items as item (item.id)}
					{@const on = chosen.includes(item.id)}
					<button
						type="button"
						aria-pressed={on}
						onclick={() => (chosen = toggled(chosen, item.id))}
						class={tagClass(on)}
					>
						{item.label}
					</button>
				{/each}
			</div>
		</div>
	{/each}
</div>
