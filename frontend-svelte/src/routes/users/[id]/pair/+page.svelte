<script lang="ts">
	import Unplug from '@lucide/svelte/icons/unplug';
	import Alert from '$lib/components/ui/Alert.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import PairingShell from '$lib/components/pairing/PairingShell.svelte';
	import ProviderChoice from '$lib/components/pairing/ProviderChoice.svelte';
	import type { ActionData, PageData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();
</script>

<svelte:head>
	<title>Connect a device · Open Wearables</title>
</svelte:head>

<PairingShell title="Connect a device" lead="Choose where your health data should come from.">
	<div class="flex flex-col gap-4">
		{#if form?.message}
			<Alert>{form.message}</Alert>
		{/if}

		{#if data.providers.length === 0}
			<div class="rounded-xl border border-border bg-surface">
				<EmptyState
					icon={Unplug}
					title="Nothing to connect yet"
					description="Ask whoever sent you this link to enable a provider."
				/>
			</div>
		{:else}
			{#each data.providers as provider (provider.provider)}
				<ProviderChoice {provider} returnUrl={data.returnUrl} />
			{/each}
		{/if}
	</div>
</PairingShell>
