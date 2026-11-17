<script lang="ts">
	import ArrowRight from '@lucide/svelte/icons/arrow-right';
	import Check from '@lucide/svelte/icons/check';
	import X from '@lucide/svelte/icons/x';
	import LinkButton from '$lib/components/ui/LinkButton.svelte';
	import PairingShell from '$lib/components/pairing/PairingShell.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const what = $derived(data.provider ?? 'Your device');
</script>

<svelte:head>
	<title>{data.connected ? 'Connected' : 'Not connected'} · Open Wearables</title>
</svelte:head>

<PairingShell
	title={data.connected ? `${what} is connected` : `${what} was not connected`}
	lead={data.connected
		? 'Data will start arriving shortly.'
		: (data.message ?? 'The sign-in did not complete.')}
>
	<div class="flex flex-col items-center gap-6">
		{#if data.connected}
			<span
				aria-hidden="true"
				class="grid size-16 place-items-center rounded-full bg-success/12 text-success"
			>
				<Check size={30} />
			</span>
		{:else}
			<span
				aria-hidden="true"
				class="grid size-16 place-items-center rounded-full bg-danger/12 text-danger"
			>
				<X size={30} />
			</span>
		{/if}

		<div class="flex w-full flex-col gap-2">
			{#if data.connected && data.returnUrl}
				<LinkButton href={data.returnUrl} rel="noreferrer">
					Continue
					<ArrowRight size={16} aria-hidden="true" />
				</LinkButton>
			{/if}

			{#if data.pairAnother}
				<LinkButton href={data.pairAnother} variant="outline">Connect another device</LinkButton>
			{/if}
		</div>
	</div>
</PairingShell>
