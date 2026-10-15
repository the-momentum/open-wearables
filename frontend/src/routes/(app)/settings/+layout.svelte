<script lang="ts">
	import { page } from '$app/state';
	import TabStrip from '$lib/components/ui/TabStrip.svelte';
	import PageHeader from '$lib/components/layout/PageHeader.svelte';
	import PendingOutlet from '$lib/components/layout/PendingOutlet.svelte';
	import { resolve } from '$app/paths';
	import { activeSettingsTab, settingsTabs } from '$lib/settings/tabs';
	import type { Snippet } from 'svelte';
	import type { LayoutData } from './$types';

	let { data, children }: { data: LayoutData; children: Snippet } = $props();

	const tabs = $derived(settingsTabs(data.features));

	const active = $derived(activeSettingsTab(page.url.pathname));
</script>

<div class="flex flex-col gap-5">
	<PageHeader
		title="Settings"
		description="Credentials, providers and the people who can sign in here."
	/>

	<TabStrip label="Settings sections" {tabs} {active} />

	<PendingOutlet within={resolve('/settings')}>{@render children()}</PendingOutlet>
</div>
