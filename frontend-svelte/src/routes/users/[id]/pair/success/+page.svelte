<script lang="ts">
	import ArrowRight from '@lucide/svelte/icons/arrow-right';
	import Check from '@lucide/svelte/icons/check';
	import LinkButton from '$lib/components/ui/LinkButton.svelte';
	import PairingShell from '$lib/components/pairing/PairingShell.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const what = $derived(data.provider ?? 'Your device');
</script>

<svelte:head>
	<title>Connected · Open Wearables</title>
</svelte:head>

<PairingShell title="{what} is connected" lead="Data will start arriving shortly.">
	<div class="flex flex-col items-center gap-6">
		<span
			aria-hidden="true"
			class="grid size-16 place-items-center rounded-full bg-success/12 text-success"
		>
			<Check size={30} />
		</span>

		<div class="flex w-full flex-col gap-2">
			{#if data.returnUrl}
				<LinkButton href={data.returnUrl} rel="noreferrer">
					Continue
					<ArrowRight size={16} aria-hidden="true" />
				</LinkButton>
			{/if}

			<LinkButton href={data.pairAnother} variant="outline">Connect another device</LinkButton>
		</div>
	</div>
</PairingShell>
