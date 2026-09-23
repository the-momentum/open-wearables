<script lang="ts">
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import CopyField from '$lib/components/ui/CopyField.svelte';
	import Sheet from '$lib/components/ui/Sheet.svelte';

	let { secret }: { secret?: { title: string; fields: { label: string; value: string }[] } } =
		$props();

	// Opens itself when an action hands one over, and stays dismissible after.
	let open = $state(false);
	$effect(() => {
		if (secret) open = true;
	});
</script>

{#if secret}
	<Sheet bind:open title={secret.title}>
		<div class="flex flex-col gap-4 px-4 pb-2">
			<!-- The API hashes it on the way in, so this really is the only showing. -->
			<Alert tone="warning">
				Copy this now. It is shown once and cannot be retrieved — losing it means rotating and
				updating your integration.
			</Alert>

			{#each secret.fields as field (field.label)}
				<CopyField label={field.label} value={field.value} />
			{/each}

			<div class="flex justify-end pt-1">
				<Button onclick={() => (open = false)}>I have saved it</Button>
			</div>
		</div>
	</Sheet>
{/if}
