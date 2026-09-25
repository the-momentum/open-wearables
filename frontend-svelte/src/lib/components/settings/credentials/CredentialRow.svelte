<script lang="ts">
	import type { Component, Snippet } from 'svelte';
	import { formatRelativeTime } from '$lib/utils/datetime';
	import SettingRow from '../SettingRow.svelte';

	let {
		icon: Icon,
		name,
		created,
		identifier,
		actions
	}: {
		icon: Component;
		name: string;
		created: string;
		/** The public half — a key prefix, an app id. */
		identifier: Snippet;
		actions: Snippet;
	} = $props();
</script>

<SettingRow {actions}>
	{#snippet lead()}
		<span
			aria-hidden="true"
			class="grid size-9 shrink-0 place-items-center rounded-lg bg-surface-muted text-muted-foreground"
		>
			<Icon size={16} />
		</span>
	{/snippet}

	{#snippet title()}
		<span class="truncate text-sm font-medium text-foreground">{name}</span>
	{/snippet}

	{#snippet meta()}
		{@render identifier()}
		<span>created {formatRelativeTime(created)}</span>
	{/snippet}
</SettingRow>
