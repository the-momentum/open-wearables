<script lang="ts">
	import ArrowDownUp from '@lucide/svelte/icons/arrow-down-up';
	import Watch from '@lucide/svelte/icons/watch';
	import PriorityList from '$lib/components/settings/priorities/PriorityList.svelte';
	import SaveBar from '$lib/components/settings/SaveBar.svelte';
	import ProviderLogo from '$lib/components/providers/ProviderLogo.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import { deviceIcon } from '$lib/providers/devices';
	import { providerLabel } from '$lib/providers/labels';
	import { ranked, reordered } from '$lib/settings/priorities';
	import { humanise } from '$lib/utils/text';
	import type { ActionData, PageData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	// Writable derived: it starts as the stored order and re-derives whenever the
	// server's does, so saving one list leaves the draft agreeing with it — but
	// reordering still assigns straight to it.
	let providers = $derived([...data.providers]);
	let deviceTypes = $derived([...data.deviceTypes]);

	const providersMoved = $derived(reordered(providers, data.providers, (entry) => entry.provider));
	const devicesMoved = $derived(
		reordered(deviceTypes, data.deviceTypes, (entry) => entry.device_type)
	);

	const label = (provider: string) => providerLabel(data.catalogue, provider);

	// The priority rows name providers but carry no icons, so the catalogue this
	// page already loads for their names supplies the logos too.
	const iconFor = (provider: string) =>
		data.catalogue.find((entry) => entry.provider === provider)?.icon_url ?? '';
</script>

<div class="flex flex-col gap-5">
	{#if form?.message}
		<Alert>{form.message}</Alert>
	{/if}

	<!-- Side by side once the sidebar is up; items-start so the short provider
	     list does not stretch to the device list's height. -->
	<div class="grid gap-5 lg:grid-cols-2 lg:items-start">
		<Card
			icon={ArrowDownUp}
			title="Provider priority"
			description="When two providers cover the same moment, the one higher up is the one shown."
		>
			<PriorityList
				bind:items={providers}
				label="Provider priority"
				keyOf={(entry) => entry.provider}
			>
				{#snippet row(entry)}
					{@const name = label(entry.provider)}
					<ProviderLogo
						provider={{ provider: entry.provider, name, icon_url: iconFor(entry.provider) }}
						size="md"
					/>
					<span class="truncate text-sm font-medium text-foreground">{name}</span>
				{/snippet}
			</PriorityList>
		</Card>

		<Card
			icon={Watch}
			title="Device priority"
			description="Within one provider: a watch worn all day and a phone in a pocket disagree, and this says which wins."
		>
			<PriorityList
				bind:items={deviceTypes}
				label="Device priority"
				keyOf={(entry) => entry.device_type}
			>
				{#snippet row(entry)}
					{@const Icon = deviceIcon(entry.device_type)}
					<Icon size={16} aria-hidden="true" class="shrink-0 text-muted-foreground" />
					<span class="truncate text-sm font-medium text-foreground">
						{humanise(entry.device_type)}
					</span>
				{/snippet}
			</PriorityList>
		</Card>
	</div>
</div>

<!-- Two lists, two endpoints: whichever was reordered is the one that saves. -->
{#if providersMoved}
	<SaveBar
		action="?/saveProviders"
		note="Provider order changed"
		payload={{ order: JSON.stringify(ranked(providers, 'provider', (entry) => entry.provider)) }}
	/>
{:else if devicesMoved}
	<SaveBar
		action="?/saveDeviceTypes"
		note="Device order changed"
		payload={{
			order: JSON.stringify(ranked(deviceTypes, 'device_type', (entry) => entry.device_type))
		}}
	/>
{/if}
