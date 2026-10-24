<script lang="ts">
	import Building2 from '@lucide/svelte/icons/building-2';
	import { enhance } from '$app/forms';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import TextField from '$lib/components/ui/TextField.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { createSubmitFlag, messageFrom } from '$lib/utils/forms.svelte';
	import type { ActionData, PageData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	const submit = createSubmitFlag();

	// Writable deriveds: edited freely, reset to the saved values when the page data reloads.
	let name = $derived(data.settings.organization_name ?? '');
	let logoUrl = $derived(data.settings.logo_url ?? '');
	let supportEmail = $derived(data.settings.support_email ?? '');

	const message = $derived(messageFrom(form, 'save'));
	const saved = $derived(form?.action === 'save' && 'saved' in form);
</script>

<Card
	icon={Building2}
	title="Organisation"
	description="How this instance introduces itself to the people who share data with it, for example in the Open Wearables Connect app before they connect."
>
	<form method="POST" action="?/save" class="flex flex-col gap-4" use:enhance={submit.enhance}>
		{#if message}
			<Alert>{message}</Alert>
		{/if}

		<TextField
			name="organization_name"
			label="Organisation name"
			placeholder="Acme Health"
			maxlength={100}
			bind:value={name}
		/>
		<TextField
			name="logo_url"
			label="Logo URL"
			hint="An https address of a square image. Leave empty to show the name only."
			placeholder="https://acmehealth.com/logo.png"
			type="url"
			bind:value={logoUrl}
		/>
		<TextField
			name="support_email"
			label="Support email"
			hint="Where users are told to write when they cannot connect."
			placeholder="help@acmehealth.com"
			type="email"
			bind:value={supportEmail}
		/>

		<div class="flex items-center justify-end gap-3">
			{#if saved && !submit.submitting}<span class={MICRO} role="status">Saved</span>{/if}
			<Button type="submit" disabled={submit.submitting}>
				{submit.submitting ? 'Saving…' : 'Save'}
			</Button>
		</div>
	</form>
</Card>
