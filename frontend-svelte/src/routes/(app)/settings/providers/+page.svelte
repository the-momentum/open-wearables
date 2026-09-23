<script lang="ts">
	import Plug from '@lucide/svelte/icons/plug';
	import SaveBar from '$lib/components/settings/SaveBar.svelte';
	import ProviderRow from '$lib/components/settings/providers/ProviderRow.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import { enabledMap, flipped } from '$lib/settings/providers';
	import type { ActionData, PageData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	// Writable derived: the draft starts as what the server holds and re-derives
	// when that changes, so a save leaves it agreeing rather than holding stale
	// switches — while a flipped switch still assigns straight to it.
	let draft = $derived(enabledMap(data.providers));

	const changed = $derived(flipped(data.providers, draft));
</script>

<div class="flex flex-col gap-5">
	{#if form?.message}
		<Alert>{form.message}</Alert>
	{/if}

	<Card
		icon={Plug}
		title="OAuth providers"
		description="Which services your users can connect. Disabling one hides it from the pairing page; data already synced stays."
	>
		{#if data.providers.length === 0}
			<EmptyState icon={Plug} title="No providers available" />
		{:else}
			<div class="divide-y divide-border">
				{#each data.providers as provider (provider.provider)}
					<ProviderRow
						{provider}
						enabled={draft[provider.provider] ?? provider.is_enabled}
						ontoggle={(next) => (draft = { ...draft, [provider.provider]: next })}
					/>
				{/each}
			</div>
		{/if}
	</Card>
</div>

{#if changed.length > 0}
	<SaveBar
		action="?/save"
		note="{changed.length} provider{changed.length === 1 ? '' : 's'} changed"
		payload={{ providers: JSON.stringify(draft) }}
	/>
{/if}
