<script lang="ts">
	import type { Component } from 'svelte';
	import Caption from './Caption.svelte';

	export type FieldGroup = {
		title: string;
		/** Absent where the group is named after its source rather than a subject. */
		icon?: Component;
		fields: { label: string; value: string }[];
	};

	let { groups }: { groups: FieldGroup[] } = $props();
</script>

<!-- Columns of labelled readings, grouped by subject so a reader scans a topic
     rather than an alphabet. -->
<div class="grid gap-x-6 gap-y-5 sm:grid-cols-2 lg:grid-cols-4">
	{#each groups as group (group.title)}
		<div class="flex flex-col gap-2">
			<Caption icon={group.icon}>{group.title}</Caption>
			<dl class="flex flex-col gap-1.5">
				{#each group.fields as field (field.label)}
					<div class="flex items-baseline justify-between gap-2">
						<dt class="text-xs text-muted-foreground">{field.label}</dt>
						<dd class="text-sm font-medium text-foreground tabular-nums">{field.value}</dd>
					</div>
				{/each}
			</dl>
		</div>
	{/each}
</div>
