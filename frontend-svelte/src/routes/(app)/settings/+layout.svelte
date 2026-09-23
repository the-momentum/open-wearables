<script lang="ts">
	import { page } from '$app/state';
	import TabStrip from '$lib/components/ui/TabStrip.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { SETTINGS_TABS, activeSettingsTab } from '$lib/settings/tabs';

	let { children } = $props();

	const tabs = [...SETTINGS_TABS];

	const active = $derived(activeSettingsTab(page.url.pathname));
</script>

<div class="flex flex-col gap-5">
	<div class="flex flex-col gap-0.5">
		<h1 class="text-lg font-semibold text-foreground">Settings</h1>
		<p class={MICRO}>Credentials, providers and the people who can sign in here.</p>
	</div>

	<TabStrip label="Settings sections" {tabs} {active} />

	{@render children()}
</div>
